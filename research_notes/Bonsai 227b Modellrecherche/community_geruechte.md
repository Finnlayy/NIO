# Community discussion, rumours and leaks around "Bonsai 227b" and a claimed OpenAI "Bonsai"

Research date: 2026-11-02. Reliability labels used on every item: **[official]**, **[credible reporting]**, **[rumour]**, **[unsupported]**. "Official" here means first-party material from PrismML, or a platform's own listing. Items marked "(search summary only)" were seen in a search result and not opened in full.

Bottom line for the report writer: no source found says Bonsai is an OpenAI model. "Bonsai 227b" is almost certainly a garbled form of "Bonsai 2 27B", a PrismML open-weight model released 2026-09-17. The origin of the OpenAI attribution could not be found, so it is treated as an unsupported claim, most likely a confusion.

## Where is "Bonsai 227b" or an OpenAI "Bonsai" mentioned, and what exactly is claimed?

### Takeaway
The string "Bonsai 227B" was found in exactly one place: a third-party auto-summary of a YouTube video, which itself credits Prism ML, not OpenAI. No page found anywhere claims an OpenAI model called Bonsai.

### Cited Findings
- **[official]** The real product is "Bonsai 2 27B" (body text: "Ternary Bonsai 2 27B"), published by PrismML on 2026-09-17, based on Qwen3.8 27B. The post does not mention OpenAI. — [PrismML announcement](https://prismml.com/news/bonsai-2-27b)
- **[official]** The Hugging Face card lists Prism ML as developer, Qwen3.8-27B as base, Apache 2.0 license, and 27.36B total parameters (24.35B language backbone, 2.54B embedding/LM head, 0.46B vision tower). "OpenAI-compatible" appears only in serving instructions. — [Hugging Face model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)
- **[unsupported]** The only "227B" occurrence: a summary page for the YouTube video "Qwen3.8-27B on 6GB VRAM: Bonsai 27B is HERE!" writes "Turner Bonsai 227B" and "Bonsai 227B", mixed with "27B", in the same text. It names Prism ML as the developer and does not mention OpenAI. The page gives no video date and no channel. — [youtubesummary.com, undated](https://youtubesummary.com/summary/LqpRNhAP09U)
- **[credible reporting]** Hands-on and explainer coverage writes the name "Bonsai 2 27B" and credits PrismML. MindStudio (2026-09-18) does not mention OpenAI. DataCamp (2026-09-18) mentions only an "OpenAI-style" interface. — [MindStudio test](https://www.mindstudio.ai/blog/bonsai-2-27b-real-world-test); [DataCamp](https://www.datacamp.com/blog/bonsai-2-27b)
- **[official]** PrismML's post writes the name with a space and on one line in its title. Only a table header splits "Ternary Bonsai 2" and "27B" across lines, so a "227B" reading would need the spacing to be lost in copying. — [PrismML announcement](https://prismml.com/news/bonsai-2-27b)
- **[credible reporting]** Hacker News search for "bonsai 227b" returned 0 hits (checked 2026-11-02). — [HN Algolia query](https://hn.algolia.com/api/v1/search?query=%22bonsai%20227b%22&hitsPerPage=20)
- **[credible reporting]** HN comment search for "openai bonsai" returned 12 hits and none claim OpenAI made Bonsai. In simonw's 2026-09-17 comment, the match is only the `llm openai endpoint` CLI command. In coolwulf's 2026-06-05 comment, "Bonsai" is a local agentic harness and OpenAI is named only for raising API prices. The other 10 are unrelated (a username, a hosted Elasticsearch service, Microsoft's acquisition, and others). — [HN Algolia query](https://hn.algolia.com/api/v1/search?query=openai%20bonsai&tags=comment&hitsPerPage=20)
- **[credible reporting]** The two main HN threads are about PrismML's releases: "Bonsai 27B" (2026-07-14, 706 points, 250 comments) and "Bonsai 2 27B" (2026-09-17, 589 points, 200 comments). No comment in the Bonsai 2 thread attributes the model to OpenAI or writes "227B". — [HN search](https://hn.algolia.com/api/v1/search?query=bonsai%2027b&hitsPerPage=20); [HN thread data](https://hn.algolia.com/api/v1/items/49746618)

### Inferences
- "227b" is very likely "2 27B" with the space dropped. The summary page's "Turner Bonsai" also looks like a speech-to-text error for "Ternary Bonsai", which suggests the summary came from an auto-transcript. A spoken "two twenty-seven B" would produce the same result. This is an inference, not something the page states.
- The video's title and the summary's 83.9 score match the September release, so the video probably dates from after 2026-09-17. The score matches [PrismML's post](https://prismml.com/news/bonsai-2-27b), but this dating is an inference.
- There is no such thing as a 227-billion-parameter Bonsai in any source found. The published count is about 27B.

### Gaps
- The YouTube video itself, its channel and its date were not checked, so the actual wording spoken in it is unknown.
- The specific post or message where the requester saw "Bonsai 227b is an OpenAI model" was not found. Without it, the claim cannot be traced to a first source.

## Could it be a stealth or anonymous model, a leaked codename, or an internal name?

### Takeaway
No evidence supports any of these. The model is publicly listed under PrismML with open weights, so nothing about it is anonymous, and Bonsai does not appear among the OpenAI codenames circulating in 2026.

### Cited Findings
- **[official]** OpenRouter lists "Ternary Bonsai 2 27B" under its named `prism-ml` author path. This is an ordinary listing, not a stealth entry. — [OpenRouter listing](https://openrouter.ai/prism-ml/ternary-bonsai-2-27b)
- **[official]** OpenRouter's stealth category is a separate section and was seen listing other names (Ox Alpha, Space Bunny Alpha), with no Bonsai entry in the results seen (search summary only). — [OpenRouter stealth page](https://openrouter.ai/stealth); [comparison page](https://openrouter.ai/compare/prism-ml/ternary-bonsai-2-27b/stealth/space-bunny-alpha)
- **[rumour]** OpenAI names that do circulate as of October 2026 include "GPT-6.2 Bel", "aurora-red/green/blue-alpha", "Doug" and "Astra Cyber". None is related to Bonsai. These come from low-tier blogs and are themselves unverified (search summary only). — [OrcaRouter on Bel](https://www.orcarouter.ai/blog/gpt-6-2-bel-leak); [Aurora report](https://pasqualepillitteri.it/de/news/25360/aurora-red-green-blue-alpha-openai-api-de); [teamorouter on GPT-6.5](https://teamorouter.com/blogs/gpt-6-5-api)
- **[credible reporting]** A guide to OpenAI's arena codenames lists Zenith, Summit, Vortex and Zephyr. Its title has no Bonsai, and it was not opened in full (search summary only). — [NxCode guide](https://www.nxcode.io/resources/news/openai-chatbot-arena-codenames-zenith-summit-vortex-zephyr-complete-guide-2026)
- **[official]** "OpenAI-compatible" and "OpenAI-style" refer to the API format used to serve the model. — [Hugging Face model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf); [DataCamp](https://www.datacamp.com/blog/bonsai-2-27b)
- **[credible reporting]** Other unrelated "Bonsai" products exist, including a Microsoft acquisition and a local agent harness, which adds to name confusion. — [HN Algolia query](https://hn.algolia.com/api/v1/search?query=openai%20bonsai&tags=comment&hitsPerPage=20)

### Inferences
- The most plausible route to an "OpenAI" label is the "OpenAI-compatible" wording in setup guides, read by a person or an LLM as attribution. A second possible route is LLM summaries of the name. Both are hypotheses; no source shows this happening.
- An open-weight model has checkable provenance, so the stealth or leak theories have little room. Base model and license are public.

### Gaps
- LMArena's model list was not opened directly. Searches found no Bonsai listing there, which is weak evidence only.
- OpenRouter's fetched page showed no provider or date details. Pricing of $0.075 input and $0.50 output per million tokens came from a search summary only.

## Who first made the claim, and is that source reliable?

### Takeaway
No first source for "Bonsai is an OpenAI model" was found. The earliest datable name chain runs from PrismML's own releases; the earliest "227B" text is the undated youtubesummary.com page, a low-reliability auto-summary that does not make the OpenAI claim.

### Cited Findings
- **[credible reporting]** PrismML came out of stealth around March–April 2026 with a 1-bit LLM family. — [HPCwire/AIwire, 2026-04-06](https://www.hpcwire.com/aiwire/2026/04/06/prismml-emerges-from-stealth-with-1-bit-llm-family/)
- **[credible reporting]** Bonsai 27B (first generation) was on HN on 2026-07-14, and Bonsai 2 27B on 2026-09-17. — [HN search](https://hn.algolia.com/api/v1/search?query=bonsai%2027b&hitsPerPage=20)
- **[credible reporting]** PrismML is described as a Caltech spinout led by professor Babak Hassibi, with investors including Khosla Ventures and Cerberus. Funding figures differ across outlets ($16.25M vs about $22M). None of the results listed OpenAI as an investor or partner (search summary only). — [Dealroom](https://dealroom.co/news/152150-prismml-raises-22m-seed-to-shrink-ai-models-onto-your-phone/); [Startup Fortune, 2026-07-15](https://startupfortune.com/a-caltech-startup-shrank-a-27-billion-parameter-ai-model-to-fit-on-an-iphone/)
- **[unsupported]** The "227B" text source has no author, channel or date. — [youtubesummary.com](https://youtubesummary.com/summary/LqpRNhAP09U)

### Inferences
- The claim does not match the profile of a known leak. No leaker, employee or reporter is attached to it, and no account or post could be identified.
- With no origin found, the claim's status is "unsupported", and the public record contradicts it directly.

### Gaps
- X/Twitter, Discord and YouTube could not be searched directly. A post may exist there that the web index does not surface. See the search log at the end of the next section.

## Is there any sign of hype, hoax, scam or AI-generated content?

### Takeaway
No hoax or scam tied to the "227b" name was found. The real risks are content-farm noise around the Bonsai name and an unrelated BONSAI token that could be misused.

### Cited Findings
- **[credible reporting]** A separate "BONSAI" token exists, described as a Lens Protocol ecosystem community token. Results did not link it to PrismML (search summary only). — [FXEmpire token profile](https://www.fxempire.it/crypto/bonsai-token/profile)
- **[unsupported]** No result reports a PrismML token or a fake Bonsai download (search summary only). This is an empty result for the query listed below, not proof that none exists.
- **[credible reporting]** Fake AI-branded tokens are a documented general pattern, such as tokens using the ChatGPT name. — [CryptoSlate](https://cryptoslate.com/?p=301572)
- **[official]** The distribution channels confirmed in this research are the `prism-ml` Hugging Face organization and prismml.com. — [Hugging Face model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf); [PrismML announcement](https://prismml.com/news/bonsai-2-27b)
- **[unsupported]** High-volume gateway blogs repeat Bonsai content in many languages, for example one OrcaRouter article across more than a dozen locales. This is mass SEO content, though no false claim was found in it. — [OrcaRouter](https://www.orcarouter.ai/de/blog/bonsai-2-vs-bonsai-27b)
- **[unsupported]** Third-party repackaging exists, such as a personal Docker Hub image. Its contents were not examined and nothing suggests it is malicious, but it is not an official channel as far as seen. — [Docker Hub listing](https://hub.docker.com/r/emmaylots/prismml-llama-bonsai)

### Inferences
- The "OpenAI Bonsai" framing looks more like an accidental error than a deliberate hoax, since no promotion, token or download is attached to it. That could change if a specific post turns up.
- Anyone offering a "Bonsai 227b" download or an "OpenAI Bonsai" token should be treated as suspect, because that product does not exist in any first-party source.

### Gaps
- Crypto tooling and domain checks for "bonsai227b"-style names were not run. Web queries returned nothing.

### Search log (exact queries, 2026-11-02)
- Web search: `"Bonsai 227b"`; `OpenAI Bonsai model leak`; `Bonsai 227B model weights 227 billion parameters`; `"Bonsai" stealth model LMArena OpenRouter`; `bonsai 227b reddit LocalLLaMA`; `"Bonsai" OpenAI model claim PrismML not OpenAI`; `"Bonsai 2" 27B Hacker News OR reddit discussion tested`; `Bonsai AI token crypto PrismML scam fake download`; `"bonsai227b" OR "bonsai-227b" OR "Bonsai-227B" OR "Bonsai 227B" OpenAI`; `OpenAI codename leak October 2026 new model testingcatalog`; `PrismML founders Caltech funding Bonsai Babak Hassibi`; `ChatGPT "Bonsai" model OpenAI rumor X Twitter leak`.
- HN Algolia: `bonsai 27b` (20 hits returned), `"bonsai 227b"` (0 hits), `openai bonsai` in comments (12 hits, none relevant to the claim).
- Reddit direct search of r/LocalLLaMA: failed, the fetch tool cannot reach reddit.com. r/OpenAI and r/singularity were not reachable the same way. Reddit coverage came only from search results and a snapshot mirror, which showed PrismML Bonsai threads and no 227B mention.
- Local project: a case-insensitive grep for "bonsai" in the NIO repo found no matches, so the claim does not come from project files.
- Not searched directly: X/Twitter, Discord, YouTube, LMArena.

## Have people actually tested it, and what did they report?

### Takeaway
Yes, many people tested Bonsai 2 27B, as a PrismML model. It runs on modest hardware at usable speeds, but reports show looping, weak agentic work and real doubt about the "near-lossless" claim. Nobody tested a "227B" model, because none exists in the record.

### Cited Findings
- **[official]** PrismML claims 98.2% retention of Qwen3.8 27B aggregate performance, scoring 83.9 versus 85.4 in thinking mode, at about 5.9 GB. — [PrismML announcement](https://prismml.com/news/bonsai-2-27b)
- **[official]** The Hugging Face card gives different figures: 84.78 versus 86.32 FP16 (also 98.2%) across 14 benchmarks, with 5.95 GB versus about 54 GB. The two first-party figure sets differ although the ratio matches. — [Hugging Face model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)
- **[credible reporting]** MindStudio's 2026-09-18 test: it missed a planted time-zone bug, a generated page's reset button never worked after three correction rounds, multilingual translation looped on languages such as Tamil, and vision plus creative writing was a clear pass. It stresses that the benchmark figures are vendor numbers. — [MindStudio](https://www.mindstudio.ai/blog/bonsai-2-27b-real-world-test)
- **[rumour]** Community speed reports on HN (2026-09-17 to 19, self-reported, unverified): about 20 tok/s on M5 Pro, 7–8 tok/s on a 16 GB M2 Mac Mini, about 89 tok/s on an RX 7900 XTX with speculative decoding, about 120 tok/s on RTX 6000 Blackwell, and 0.67 tok/s on a 6 GB GPU. — [HN thread data](https://hn.algolia.com/api/v1/items/49746618)
- **[rumour]** Community quality reports: Aurornis said "The most common failure mode is that it goes into loops"; v3ss0n said "On actual agentic task , it just fail."; simonw called an SVG test "Pretty decent for a 5.5GB model file"; jedbrooke found it felt "smarter than Bonsai 1 27B". redox99 disputed the "near lossless" description. — [HN thread data](https://hn.algolia.com/api/v1/items/49746618)
- **[rumour]** Compatibility problems: an Intel B70 user got nothing usable because Prism's llama.cpp fork lacks SYCL kernels, an RX 9070 user could not get it working, and the browser demo crashed on Pixel 9 Pro phones. — [HN thread data](https://hn.algolia.com/api/v1/items/49746618)
- **[unsupported]** DataCamp cites a third-party knowledge-and-reasoning composite of about 79.9 versus 85.6 for FP16, without naming the reviewers or methods. It also mentions community reports of recall loss past about 200K tokens, without sources. — [DataCamp](https://www.datacamp.com/blog/bonsai-2-27b)

### Inferences
- The behaviour reported fits a heavily quantized Qwen model. No report points to OpenAI-like provenance, and the public base model settles that question.

### Gaps
- No independent, reproducible benchmark with full methodology was found. Community numbers are self-reported.
- Nobody was found testing self-identification (asking the model who made it). A Qwen-derived model could in principle give a wrong answer, but this is speculation, and no such report was found.
</content>
</invoke>
