# Bonsai 227b: primary-source check of existence and OpenAI attribution

Research date: 2026-11-02. Method note: page contents were read through a fetch tool that summarises pages with a small model. "Does not appear" for a web page means the tool found no mention, not that a raw text grep was run. The Hugging Face API, Ollama and GitHub results are direct listings or search results.

## Does the exact name "Bonsai 227b" appear in any official source?

### Takeaway
No. No official source, model repository or registry checked contains "Bonsai 227b" in any spelling. The closest real name is PrismML's "Bonsai 2 27B" (full name "Ternary Bonsai 2 27B"), and "227b" is most likely that name with the space lost.

### Cited Findings
- The Hugging Face search for "bonsai" (100 most recently modified models, back to about 2026-10-16) returned no model ID containing "227"; the only "227" matches were in download counts — [HF API, search=bonsai](https://huggingface.co/api/models?search=bonsai&limit=100&sort=lastModified)
- The Hugging Face search for "227b" returned 9 repos, all with hash-like or unrelated names (for example `ErrorAI/227bef2b-...`); none relates to Bonsai — [HF API, search=227b](https://huggingface.co/api/models?search=227b&limit=50)
- All 42 repos listed for the `prism-ml` organisation use the sizes 1.7B, 2B, 4B, 8B, 9B and 27B; none is named 227B — [HF API, author=prism-ml](https://huggingface.co/api/models?author=prism-ml&limit=100)
- The Ollama search for "bonsai" shows no model with "227" in its name — [Ollama search](https://ollama.com/search?q=bonsai)
- The official Ollama `bonsai-2` entry has the tags latest, 2b, 4b, 9b and 27b; there is no 227b tag — [Ollama library: bonsai-2](https://ollama.com/library/bonsai-2)
- `gh search repos` for "bonsai-227b" and "bonsai 227b" returned an empty list for both queries (command run 2026-11-02, GitHub repository search).
- A web search for the spellings "bonsai-227b", "bonsai227b", "Bonsai 227B" and "bonsai 2.27b" found no exact match; results resolved to Bonsai 2 27B, Bonsai 27B or unrelated uses of "bonsai" — [example: CloudPrice listing](https://cloudprice.net/models/prism-ml-bonsai-2-27b)
- An arXiv query for "Bonsai" with quantization or language model returned 4 papers; neither "PrismML" nor "227" appears in the entries — [arXiv API](https://export.arxiv.org/api/query?search_query=all:%22Bonsai%22+AND+(all:quantization+OR+all:%22language+model%22)&sortBy=submittedDate&sortOrder=descending&max_results=25)

### Inferences
- "Bonsai 227b" is very likely a garbled "Bonsai 2 27B" (generation 2, 27B size). This is an inference from name similarity; no source documents the misspelling.

### Gaps
- Papers with Code was not checked separately.
- The exact origin of the name "227b" in what the user was told is unknown, because the original source was not supplied.
- The Hugging Face "bonsai" listing covered 100 rows, not the full result set. Older repos could exist beyond that window, though the separate "227b" search and the full `prism-ml` listing reduce this risk.

## Does OpenAI mention any model, project or codename "Bonsai"?

### Takeaway
No evidence found. Bonsai does not appear in OpenAI's model list, deprecations page or Hugging Face organisation, and the OpenAI-domain hits for the word are unrelated. The attribution to OpenAI is unsupported, though an unannounced internal codename cannot be excluded.

### Cited Findings
- OpenAI's current model page lists the GPT-6 family, GPT-Image-2.5, GPT-Realtime and similar models; "Bonsai" does not appear — [OpenAI API docs: Models](https://developers.openai.com/api/docs/models)
- OpenAI's deprecations page does not mention "Bonsai" (latest entries dated 2026-10-14) — [OpenAI deprecations](https://developers.openai.com/api/docs/deprecations)
- None of the 39 model IDs in OpenAI's Hugging Face organisation contains "bonsai"; they include gpt-oss, whisper, CLIP and privacy-filter — [HF API, author=openai](https://huggingface.co/api/models?author=openai&limit=100)
- No repo name in the OpenAI GitHub organisation contains "bonsai" (`gh api orgs/openai/repos`, filtered with grep, 2026-11-02).
- GitHub code search `org:openai bonsai` returned exactly 1 hit, a prompts data file in the CLIP repo, which is not a model reference by its location (file not opened) — [openai/CLIP data/prompts.md](https://github.com/openai/CLIP/blob/d05afc436d78f1c48dc0dbf8e5980a9d471f35f6/data/prompts.md)
- A domain-restricted search of OpenAI sites for "bonsai" returned only unrelated hits: a DALL-E gallery image prompt, a forum metaphor, and a mention of the separate company Bonsai Robotics in a California impact report — [OpenAI California report](https://cdn.openai.com/pdf/12082a3a-1a59-4bb9-b3e2-08a8c65849b0/OAI_California-Impact_Aug-2025.pdf), [DALL-E gallery thread](https://community.openai.com/t/official-dall-e-gallery-november-2024-smaller-things-edition/999814/15)
- OpenAI's own open-weight line is gpt-oss (120b and 20b), natively quantized in the 4-bit MXFP4 format, plus gpt-oss-safeguard; a search for a 2026 OpenAI 1-bit or low-bit release found nothing — [Introducing gpt-oss](https://openai.com/index/introducing-gpt-oss/), [gpt-oss-safeguard](https://openai.com/index/introducing-gpt-oss-safeguard/)
- PrismML's Bonsai 2 27B announcement, its press release and its launch post do not mention OpenAI — [PrismML: Bonsai 2 27B](https://prismml.com/news/bonsai-2-27b), [PR Newswire release](https://www.prnewswire.com/news-releases/prismml-launches-bonsai-2-27b-its-most-capable-model-yet-302882228.html), [PrismML: launch post](https://prismml.com/news/prismml-launches-worlds-first-1-bit-ai-model)
- The only OpenAI reference on the Hugging Face model card is OpenAI-compatible serving: `llama serve` and vLLM expose a `/v1/chat/completions` endpoint — [HF model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)
- OpenRouter also describes access to the Prism ML model through an OpenAI-compatible API — [OpenRouter: Prism ML](https://openrouter.ai/prism-ml)

### Inferences
- A plausible source of the claim is the phrase "OpenAI-compatible", which describes an API format and not who made the model. This is a hypothesis; no page was found that makes the mistaken attribution.
- A search phrased to find such confusion found no source that says Bonsai comes from OpenAI.

### Gaps
- Internal or unannounced OpenAI codenames cannot be ruled out from public sources.
- OpenAI system cards and research papers were not checked individually; coverage comes from the domain-restricted search, which is not a complete index of openai.com.
- A secondary-search summary says Khosla Ventures, PrismML's lead investor, was also an early OpenAI investor. The underlying page was not opened, and this would be a shared investor at most, not a product link. It is unverified here.

## Who publishes the real model, and what are its specs?

### Takeaway
The real model is Ternary Bonsai 2 27B from PrismML (Pasadena, Caltech origins), released 2026-09-17 under Apache 2.0. It is a ternary-quantized derivative of Qwen3.8 27B, about 5.9 GB in size, and its benchmarks are vendor-reported.

### Cited Findings
**Publisher and company**
- PrismML (Prism ML, Inc.), Pasadena, California; founder and CEO is Babak Hassibi, a Caltech professor — [PrismML launch post](https://prismml.com/news/prismml-launches-worlds-first-1-bit-ai-model)
- The release names Khosla Ventures, Cerberus and Google as investors or backers, with continuing support from Samsung, and Ion Stoica as advisor — [PR Newswire](https://www.prnewswire.com/news-releases/prismml-launches-bonsai-2-27b-its-most-capable-model-yet-302882228.html)
- The March launch post names Khosla Ventures and Cerberus Ventures as investors and describes Google and Caltech as compute grant providers; the two statements on Google's role differ — [PrismML launch post](https://prismml.com/news/prismml-launches-worlds-first-1-bit-ai-model)

**Date, licence, base**
- Announced 2026-09-17 — [PrismML](https://prismml.com/news/bonsai-2-27b); the main HF repo was created 2026-09-16T23:40 UTC — [HF API](https://huggingface.co/api/models?author=prism-ml&limit=100)
- Licence Apache 2.0; derived from Qwen/Qwen3.8-27B with unchanged architecture — [HF model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)
- Trained on Google v5 TPUs — [PR Newswire](https://www.prnewswire.com/news-releases/prismml-launches-bonsai-2-27b-its-most-capable-model-yet-302882228.html)

**Parameters and architecture**
- 27.36B total (24.35B language backbone, 2.54B embedding/LM head, 0.46B vision tower) — [HF model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf); the press release says 27.8B — [PR Newswire](https://www.prnewswire.com/news-releases/prismml-launches-bonsai-2-27b-its-most-capable-model-yet-302882228.html)
- Hybrid attention (about 75% linear, 25% full), SwiGLU MLP, RoPE, RMSNorm; 262K-token context; multimodal text and image input — [HF model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf), [PrismML](https://prismml.com/news/bonsai-2-27b)

**Quantization and files**
- Ternary weights {-1, 0, +1} with FP16 group scales; 1.72 effective bits per weight on the HF card, 1.76 on the PrismML page — [HF model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf), [PrismML](https://prismml.com/news/bonsai-2-27b)
- Formats: PTQ1_0 5.95 GB (PrismML llama.cpp fork), PQ2_0 7.21 GB (fork), Q2_0 7.63 GB (stock llama.cpp b11556 or newer), optional vision mmproj 0.63 GB, FP16 reference about 54 GB. The fetch noted that the card's file listing shows different sizes for some files — [HF model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)
- The Ollama 27b tag is 8.3 GB — [Ollama](https://ollama.com/library/bonsai-2)

**Benchmarks (all vendor-reported)**
- 20-benchmark aggregate: 83.9 against 85.4 for Qwen3.8 27B, or 98.2% — [PrismML](https://prismml.com/news/bonsai-2-27b)
- HF card, 14 thinking-mode benchmarks: 84.78 against 86.32 for FP16, also stated as 98.2%; math 96.57, coding 89.42, instruction following 82.66, BFCL v3 tool calling 74.92, vision 66.19 — [HF model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)
- A secondary test claims weak self-correction in code generation and failures in translation; it is a blog, not a controlled evaluation — [MindStudio test](https://www.mindstudio.ai/blog/bonsai-2-27b-real-world-test)

**Hardware and speed**
- No formal minimum is stated; the language model needs roughly 6 to 7.6 GB resident depending on format — [HF model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)
- Up to 143 tok/s on RTX 5090 and 46.8 tok/s on M5 Max (PrismML) — [PrismML](https://prismml.com/news/bonsai-2-27b); about 130 tok/s on RTX 5090 with PQ2_0, about 28 tok/s on M5 Pro (HF card) — [HF model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)

**Where to get it**
- Weights: [HF repo](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) and [HF MLX build](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-mlx-2bit); Ollama: [bonsai-2](https://ollama.com/library/bonsai-2); hosted: [OpenRouter](https://openrouter.ai/prism-ml)
- PrismML also lists the GitHub repo PrismML-Eng/Bonsai-demo and docs at docs.prismml.com — [PrismML](https://prismml.com/news/bonsai-2-27b)

**Family timeline**
- 1-bit Bonsai 8B, 4B and 1.7B announced 2026-03-31 — [PrismML](https://prismml.com/news/prismml-launches-worlds-first-1-bit-ai-model)
- Bonsai Image 4B repos created May 2026; first-generation Bonsai 27B repos created 2026-07-04; Bonsai 2 9B, 4B and 2B repos created 2026-09-23 — [HF API](https://huggingface.co/api/models?author=prism-ml&limit=100)

### Inferences
- Independent evaluation is thin, so the 98.2% retention figure should be treated as a vendor claim. The same percentage rests on two different benchmark suites (20 and 14).
- Community repos such as `BoldingBuilds/...` and `3hs4n/...` are third-party derivatives, not PrismML releases.

### Gaps
- The seed amount is unresolved: PrismML's launch post gives no figure, and secondary listings differ — [$16.3M listing](https://www.trysignalbase.com/news/funding/prismml-raises-163m-seed-round), [$22M listing](https://dealroom.co/news/152150-prismml-raises-22m-seed-to-shrink-ai-models-onto-your-phone/). Neither page was opened.
- The PrismML whitepaper was not read directly.
- PrismML's page does not name the developer of Qwen3.8. A secondary source calls it Alibaba's — [MindStudio](https://www.mindstudio.ai/blog/ternary-bonsai-2-27b-2bit-model). The model name is given as spelled in the sources.
- The difference between 27.36B and 27.8B parameters is not explained by any source read.

## Does "227b" plausibly mean 227 billion parameters?

### Takeaway
Nothing supports that reading. No Bonsai model has 227B parameters; the largest size in the family is 27B, and "2 27B" reads as generation 2, 27 billion parameters.

### Cited Findings
- PrismML's naming is generation plus size: Bonsai 2 comes in 27B, 9B, 4B and 2B — [Ollama](https://ollama.com/library/bonsai-2), [HF API](https://huggingface.co/api/models?author=prism-ml&limit=100)
- The "27B" is confirmed as parameter size by the card's 27.36B total — [HF model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)
- For comparison, OpenAI's `gpt-oss-120b` lists about 116.8B parameters, so a "227b" name would also not fit its gpt-oss sizes — [HF API: gpt-oss-120b](https://huggingface.co/api/models/openai/gpt-oss-120b)

### Inferences
- "227b" as 227 billion parameters is most likely an artefact of reading "2 27B" as one number. This is an inference, not a documented fact.

### Gaps
- Without the original source of the claim, it cannot be confirmed which model the speaker meant. A different, undisclosed model under that name is unlikely but not disprovable.
