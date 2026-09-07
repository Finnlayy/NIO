import logging
import json
import os
import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class GenAIClient:
    """Gemini GenAI integration for reflection, journal generation, and DSR."""

    def __init__(self, config):
        self.api_key = config.GEMINI_API_KEY
        self.model_fast = config.GEMINI_MODEL_FAST
        self.model_deep = config.GEMINI_MODEL_DEEP
        self.runtime_dir = Path("Architect/runtime/reflections")
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

        # LM Studio (local AI supply — fallback for token exhaustion / rate limits)
        self.lm_studio_enabled = getattr(config, "LM_STUDIO_ENABLED", True)
        self.lm_studio_url = getattr(config, "LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions")
        self.lm_studio_model = getattr(config, "LM_STUDIO_MODEL", "local-model")
        self.lm_studio_api_key = getattr(config, "LM_STUDIO_API_KEY", "not-needed")
        self.lm_studio_timeout = getattr(config, "LM_STUDIO_TIMEOUT", 30.0)

        # Initialize LM Studio client (uses OpenAI-compatible endpoint)
        self.lm_client = None
        if self.lm_studio_enabled:
            try:
                import requests
                # Quick connectivity probe
                resp = requests.get(
                    self.lm_studio_url.replace("/v1/chat/completions", "/v1/models"),
                    timeout=2.0,
                    headers={"Authorization": f"Bearer {self.lm_studio_api_key}"},
                )
                # If endpoint responds (even 404 or 401), LM Studio is present
                if resp.status_code in (200, 404, 401, 422):
                    self.lm_client = True
                    logger.info("LM Studio detected at %s (status %s); ready as AI supply fallback.", self.lm_studio_url, resp.status_code)
                else:
                    self.lm_client = False
            except Exception as exc:
                self.lm_client = False
                logger.info("LM Studio not reachable at %s (%s); will rely on stub if Gemini fails.", self.lm_studio_url, exc)
        else:
            self.lm_client = False

        try:
            from google import genai
            if self.api_key:
                self.client = genai.Client(api_key=self.api_key)
                self.real_client = True
            else:
                self.client = None
                self.real_client = False
                logger.warning("GEMINI_API_KEY not set; GenAIClient will use structured stub mode.")
        except ImportError:
            self.client = None
            self.real_client = False
            logger.warning("google-genai SDK not found, using structured stub mode.")

    def _call_lm_studio(self, prompt: str) -> str:
        """Call LM Studio (OpenAI-compatible endpoint) as AI supply fallback."""
        if not self.lm_client:
            return None
        try:
            import requests
            payload = {
                "model": self.lm_studio_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 1024,
            }
            headers = {
                "Content-Type": "application/json",
            }
            if self.lm_studio_api_key and self.lm_studio_api_key != "not-needed":
                headers["Authorization"] = f"Bearer {self.lm_studio_api_key}"
            response = requests.post(
                self.lm_studio_url,
                headers=headers,
                json=payload,
                timeout=self.lm_studio_timeout,
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content", "")
                if content:
                    logger.info("LM Studio returned content (%d chars)", len(content))
                    return content
            text = data.get("text") or data.get("output")
            if text:
                return text
            logger.warning("LM Studio response format unexpected: %s", str(data)[:200])
            return None
        except Exception as exc:
            logger.error("LM Studio call failed: %s", exc)
            return None

    def generate_journal(self, context: dict) -> dict:
        """Generate a structured journal entry from execution context."""
        if not isinstance(context, dict):
            context = {"raw": str(context)}

        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        context_str = json.dumps(context, indent=2, ensure_ascii=False)

        if self.real_client and self.client:
            try:
                prompt = (
                    "You are OMEGA's reflection engine. Generate a concise journal entry "
                    "based on the following execution context. Include: (1) summary, "
                    "(2) key observations, (3) anomalies detected, (4) next-step hypothesis. "
                    f"\n\nContext:\n{context_str}\n"
                )
                response = self.client.models.generate_content(
                    model=self.model_deep,
                    contents=prompt,
                )
                output_text = response.text
                output_structured = {
                    "timestamp": timestamp,
                    "source": "gemini_deep",
                    "mode": "real",
                    "output": output_text,
                    "context_reference": context.get("job_id") or context.get("plan_id") or "unknown",
                    "structured_insights": {
                        "summary": output_text[:500],
                        "observations": [line.strip() for line in output_text.split("\n") if line.strip() and len(line) < 200],
                        "anomalies": [],
                        "hypothesis": output_text[-500:] if len(output_text) > 500 else output_text,
                    },
                }
            except Exception as exc:
                logger.error("Gemini API call failed in generate_journal: %s", exc)
                lm_output = self._call_lm_studio(
                    f"Generate a concise journal entry based on this execution context: "
                    f"{context_str}\nInclude: summary, observations, anomalies, hypothesis."
                )
                if lm_output:
                    output_structured = {
                        "timestamp": timestamp,
                        "source": "lm_studio",
                        "mode": "fallback_real",
                        "output": lm_output,
                        "context_reference": context.get("job_id") or context.get("plan_id") or "unknown",
                        "structured_insights": {
                            "summary": lm_output[:500],
                            "observations": [line.strip() for line in lm_output.split("\n") if line.strip() and len(line) < 200],
                            "anomalies": [],
                            "hypothesis": lm_output[-500:] if len(lm_output) > 500 else lm_output,
                        },
                    }
                else:
                    output_structured = self._stub_journal(context, timestamp, error=f"gemini_failed: {exc}; lm_studio_unavailable: true")
        else:
            # Even without Gemini SDK, try LM Studio as primary AI supply
            lm_output = self._call_lm_studio(
                f"Generate a concise journal entry based on this execution context: {context_str}\n"
                "Include: summary, observations, anomalies, hypothesis."
            )
            if lm_output:
                output_structured = {
                    "timestamp": timestamp,
                    "source": "lm_studio",
                    "mode": "fallback_real",
                    "output": lm_output,
                    "context_reference": context.get("job_id") or context.get("plan_id") or "unknown",
                    "structured_insights": {
                        "summary": lm_output[:500],
                        "observations": [line.strip() for line in lm_output.split("\n") if line.strip() and len(line) < 200],
                        "anomalies": [],
                        "hypothesis": lm_output[-500:] if len(lm_output) > 500 else lm_output,
                    },
                }
            else:
                output_structured = self._stub_journal(context, timestamp, error="gemini_not_configured; lm_studio_unavailable")

        # Persist to runtime file for audit trail
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"journal_{timestamp.replace(':', '-')}.json"
        file_path = self.runtime_dir / file_name
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(output_structured, f, indent=2, ensure_ascii=False)
            logger.info("Journal saved to %s", file_path)
        except Exception as exc:
            logger.error("Failed to persist journal to %s: %s", file_path, exc)

        return output_structured

    def reflect_dsr(self, post_mortem_data: dict) -> dict:
        """Generate a structured DSR (Diagnosis, Summary, Recommendation) reflection."""
        if not isinstance(post_mortem_data, dict):
            post_mortem_data = {"raw": str(post_mortem_data)}

        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        pm_str = json.dumps(post_mortem_data, indent=2, ensure_ascii=False)

        if self.real_client and self.client:
            try:
                prompt = (
                    "You are OMEGA's post-mortem reflection engine (DSR: Diagnosis, Summary, Recommendation). "
                    "Analyze the following post-mortem data and produce a structured reflection with these exact sections: "
                    "1) DIAGNOSIS (root cause), 2) SUMMARY (what happened), 3) RECOMMENDATION (corrective actions), "
                    "4) CONFIDENCE (0.0-1.0), 5) RISK_FLAGS (list of risk concerns). "
                    f"\n\nPost-Mortem Data:\n{pm_str}\n"
                )
                response = self.client.models.generate_content(
                    model=self.model_deep,
                    contents=prompt,
                )
                output_text = response.text
                output_structured = self._parse_dsr_output(output_text, timestamp, post_mortem_data, mode="real")
            except Exception as exc:
                logger.error("Gemini API call failed in reflect_dsr: %s", exc)
                lm_output = self._call_lm_studio(
                    f"Analyze this post-mortem data and produce a structured reflection (DSR): "
                    f"DIAGNOSIS, SUMMARY, RECOMMENDATION, CONFIDENCE (0.0-1.0), RISK_FLAGS.\n"
                    f"Data: {pm_str}\n"
                )
                if lm_output:
                    output_structured = self._parse_dsr_output(lm_output, timestamp, post_mortem_data, mode="lm_studio_fallback")
                    output_structured["source"] = "lm_studio"
                    output_structured["mode"] = "fallback_real"
                    output_structured["raw_output"] = lm_output
                else:
                    output_structured = self._stub_dsr(post_mortem_data, timestamp, error=f"gemini_failed: {exc}; lm_studio_unavailable: true")
        else:
            # Try LM Studio when Gemini not available (primary supply in this case)
            lm_output = self._call_lm_studio(
                f"Analyze this post-mortem data and produce a structured reflection (DSR): "
                f"DIAGNOSIS, SUMMARY, RECOMMENDATION, CONFIDENCE (0.0-1.0), RISK_FLAGS.\n"
                f"Data: {pm_str}\n"
            )
            if lm_output:
                output_structured = self._parse_dsr_output(lm_output, timestamp, post_mortem_data, mode="lm_studio_primary")
                output_structured["source"] = "lm_studio"
                output_structured["mode"] = "real"
                output_structured["raw_output"] = lm_output
            else:
                output_structured = self._stub_dsr(post_mortem_data, timestamp, error="gemini_not_configured; lm_studio_unavailable")

        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"dsr_{timestamp.replace(':', '-')}.json"
        file_path = self.runtime_dir / file_name
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(output_structured, f, indent=2, ensure_ascii=False)
            logger.info("DSR reflection saved to %s", file_path)
        except Exception as exc:
            logger.error("Failed to persist DSR to %s: %s", file_path, exc)

        return output_structured

    def _stub_journal(self, context, timestamp, error=None):
        return {
            "timestamp": timestamp,
            "source": "structured_stub",
            "mode": "stub",
            "error": error,
            "output": f"Stub journal for context: {str(context)[:200]}...",
            "structured_insights": {
                "summary": f"Stub summary for job/plan reference: {context.get('job_id') or context.get('plan_id') or 'unknown'}.",
                "observations": ["Stub observation 1: execution completed", "Stub observation 2: no anomalies detected"],
                "anomalies": [],
                "hypothesis": "No real reflection available; review execution metrics manually.",
            },
        }

    def _stub_dsr(self, post_mortem_data, timestamp, error=None):
        diagnosis = f"Stub diagnosis based on post-mortem reference: {post_mortem_data.get('job_id') or post_mortem_data.get('execution_result', 'unknown')}."
        return {
            "timestamp": timestamp,
            "source": "structured_stub",
            "mode": "stub",
            "error": error,
            "post_mortem_reference": post_mortem_data.get("job_id") or post_mortem_data.get("execution_result", "unknown"),
            "structured_reflection": {
                "diagnosis": diagnosis,
                "summary": "Execution completed with potential anomalies; manual review required for accurate assessment.",
                "recommendation": "Run full reflection pipeline with real GenAI integration once API key is configured.",
                "confidence": 0.3,
                "risk_flags": ["stub_reflection"],
            },
        }

    def _parse_dsr_output(self, text, timestamp, post_mortem_data, mode):
        lines = text.split("\n")
        diagnosis_lines = []
        summary_lines = []
        recommendation_lines = []
        confidence = 0.5
        risk_flags = []

        current_section = None
        for line in lines:
            line_stripped = line.strip()
            lower = line_stripped.lower()
            if any(key in lower for key in ["diagnosis", "root cause"]):
                current_section = "diagnosis"
                continue
            elif any(key in lower for key in ["summary", "what happened"]):
                current_section = "summary"
                continue
            elif any(key in lower for key in ["recommendation", "corrective", "action"]):
                current_section = "recommendation"
                continue
            elif any(key in lower for key in ["confidence", "certainty"]):
                current_section = "confidence"
                # Try to extract numeric confidence from line
                try:
                    for token in line_stripped.split():
                        if token.replace(".", "", 1).isdigit():
                            confidence = float(token)
                except ValueError:
                    pass
                continue
            elif any(key in lower for key in ["risk", "flag", "concern"]):
                current_section = "risk_flags"
                continue

            if current_section == "diagnosis":
                diagnosis_lines.append(line_stripped)
            elif current_section == "summary":
                summary_lines.append(line_stripped)
            elif current_section == "recommendation":
                recommendation_lines.append(line_stripped)
            elif current_section == "risk_flags":
                if line_stripped:
                    risk_flags.append(line_stripped)

        diagnosis = " ".join(diagnosis_lines) or text[:300]
        summary = " ".join(summary_lines) or text[:500]
        recommendation = " ".join(recommendation_lines) or text[-300:] if len(text) > 300 else text
        if confidence == 0.5 and "0." in text:
            # Try simple regex-style extraction
            import re
            match = re.search(r"([0-1]\.\d+)", text)
            if match:
                confidence = float(match.group(1))
                confidence = max(0.0, min(1.0, confidence))

        return {
            "timestamp": timestamp,
            "source": "gemini_deep",
            "mode": mode,
            "post_mortem_reference": post_mortem_data.get("job_id") or post_mortem_data.get("execution_result", "unknown"),
            "structured_reflection": {
                "diagnosis": diagnosis,
                "summary": summary,
                "recommendation": recommendation,
                "confidence": confidence,
                "risk_flags": risk_flags if risk_flags else ["none_detected"],
            },
            "raw_output": text,
        }
