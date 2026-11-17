# Bonsai disambiguation: what "Bonsai 227b" might refer to

Research date: 2026-11-02. Facts carry inline sources. Anything under "Inferences" is my reasoning, not sourced fact. Model names are spelled as the sources spell them.

## Which LLMs or ML models carry the name "Bonsai"?

### Takeaway
In 2026 "Bonsai" in the LLM space means PrismML, a Caltech spinout, not OpenAI. Its open-weight, low-bit compressions of existing models come in two generations plus an image family. The only other notable ML uses of the name are older Microsoft items (a 2017 tree classifier and the Project Bonsai machine-teaching platform), and neither has LLM-style size suffixes.

### Cited Findings

**Disambiguation map**

| Name | Publisher | Date | Size variants | Type and key specs | Status |
|---|---|---|---|---|---|
| Bonsai 2 27B / "Ternary Bonsai 2 27B" | PrismML | 2026-09-17 | 27B (27.8B params) | Ternary, 5.9 GB, based on Qwen3.8 27B | Current flagship |
| Bonsai 2 9B, 4B, 2B | PrismML | Not confirmed; 27B announcement page already lists them | 9B, 4B, 2B | Ternary; 2.00 / 0.95 / 0.43 GB (PTQ1_0); Qwen3.5 bases | Current |
| Bonsai 27B (1-bit and ternary) | PrismML | 2026-07-14 | 27B | 3.9 GB 1-bit, 5.9 GB ternary; Qwen3.6-27B base | Superseded |
| 1-bit Bonsai 8B, 4B, 1.7B | PrismML | 2026-03-31 | 8B, 4B, 1.7B | 8B fits 1.15 GB; Qwen3-8B base (secondary source) | Superseded |
| Ternary-Bonsai family | PrismML | Not confirmed | 27B, 8B, 4B, 1.7B | "1.58-bit" per docs | Superseded |
| Bonsai Image 4B | PrismML | Not stated in docs | 4B | Text-to-image; 1-bit or ternary; FLUX.2 Klein 4B base | Current |
| Bonsai (tree classifier) | Microsoft Research / IIT Delhi | 2017 (older) | None; 2 KB RAM target | Shallow sparse tree for IoT devices | Academic, not an LLM |
| Project Bonsai | Microsoft (acquired startup) | Public preview May 2020 (older) | None | Low-code machine-teaching platform; models called "brains" | Current status unknown |

**PrismML details**
- Bonsai 2 27B was released 2026-09-17, is based on Qwen3.8 27B, uses ternary {−1, 0, +1} weights with FP16 group-wise scaling, has 1.76 effective bits per weight, totals 5.9 GB, and supports a 262K-token context — [PrismML](https://prismml.com/news/bonsai-2-27b)
- It is described as a 27.8-billion-parameter multimodal model, Apache 2.0, trained on Google v5 TPUs — [PrismML press release](https://prismml.com/news/prismml-launches-bonsai-2-27b)
- File sizes for the Bonsai 2 family: 27B is 5.95 GB (PTQ1_0), 7.21 GB (PQ2_0), 8.60 GB (MLX with vision tower); 9B is 2.00 GB; 4B is 0.95 GB; 2B is 0.43 GB — [PrismML docs](https://docs.prismml.com/models/bonsai-27b)
- The earlier 1-bit and 1.58-bit Ternary-Bonsai families at 27B, 8B, 4B and 1.7B are described as superseded by Bonsai 2 — [PrismML docs](https://docs.prismml.com/models/bonsai-27b)
- Bonsai 27B dated 14 July 2026: ternary 1.71 bits per weight at 5.9 GB, 1-bit 1.125 bits per weight at 3.9 GB, compression of Qwen3.6-27B rather than a new pretrain — [search summary of secondary blogs, including dsebastien.net](https://www.dsebastien.net/bonsai-27b/); the 14 July date and the 3.9 GB / 5.9 GB sizes are confirmed by [PrismML](https://prismml.com/news/bonsai-2-27b)
- 1-bit Bonsai 8B launched 2026-03-31 alongside 4B and 1.7B, 8.2 billion parameters, 1.15 GB, Apache 2.0 — [PrismML](https://prismml.com/news/prismml-launches-worlds-first-1-bit-ai-model); [PrismML technical post](https://prismml.com/news/bonsai-8b)
- Bonsai Image 4B is based on FLUX.2 Klein 4B, in 1-bit and ternary variants, Apache 2.0 — [PrismML docs](https://docs.prismml.com/models/bonsai-image)
- PrismML is led by founder and CEO Babak Hassibi, came from Caltech researchers, and names Khosla Ventures, Cerberus, Google and Samsung as backers. OpenAI is not mentioned — [PrismML press release](https://prismml.com/news/prismml-launches-bonsai-2-27b)

**Microsoft (older items)**
- Bonsai is a tree-based model from Kumar, Goyal and Varma (ICML 2017), targeting devices with 2 KB RAM — [PMLR](https://proceedings.mlr.press/v70/kumar17a.html); code in [Microsoft EdgeML](https://github.com/microsoft/EdgeML/wiki/Bonsai)
- Project Bonsai is a machine-teaching service announced in public preview at Build, May 2020 — [TechCrunch](https://techcrunch.com/2020/05/19/microsoft-launches-project-bonsai-its-new-machine-teaching-service-for-building-autonomous-systems)

**Community derivatives**
- A Hugging Face search for "bonsai" (top 100 by downloads) returns prism-ml plus many third-party repos, mostly re-quantisations and "uncensored"/"abliterated" fine-tunes of Ternary-Bonsai-2-27B, with names such as `dealignai/Bonsai-2-27B-Ternary-CRACK-GGUF` and `W-Zil/Bonsai_2_27b_VL_Uncensored-PTQ1_PTQ2-MTP` — [Hugging Face API](https://huggingface.co/api/models?search=bonsai&limit=100&sort=downloads)
- That listing shows no non-PrismML base family named Bonsai; every third-party id I reviewed is a derivative of PrismML weights or has an ambiguous name such as `dakebakery/Bonsai-JEV` — [Hugging Face API](https://huggingface.co/api/models?search=bonsai&limit=100&sort=downloads)

### Inferences
- PrismML's family is the only "Bonsai" line with LLM-style size suffixes, so it is the natural starting point for a name like "Bonsai 227b".
- Some community repos use lowercase forms such as `Bonsai_2_27b`, which sit very close to the phrase the user heard.

### Gaps
- I found no release date for Bonsai 2 9B/4B/2B or for the original Ternary-Bonsai family.
- The Hugging Face listing is capped at 100 results sorted by downloads, and the 33 prism-ml ids were not expanded individually, so rare repos may be missing.
- Whether Microsoft Project Bonsai still operates is unconfirmed; one search returned nothing on its retirement.
- My Google-specific search for a "Bonsai" model returned nothing, but the query was combined with others and is weak evidence. No Google model called Bonsai was found.

## Does any family use size suffixes that "227b" would fit, or is it a typo or mishearing?

### Takeaway
No source I found names a model "Bonsai 227b", and no Bonsai has 227 billion parameters. The best explanation is that "Bonsai 2 27B" lost its space, which fits letter for letter, but that is my inference and no source documents it.

### Cited Findings
- An exact-phrase web search for "Bonsai 227b" returned only Bonsai 2 27B and Bonsai 27B pages, none using the string "227b" — [MindStudio](https://www.mindstudio.ai/blog/ternary-bonsai-2-27b-2bit-model); [PrismML](https://prismml.com/news/bonsai-2-27b); [DataCamp](https://www.datacamp.com/blog/bonsai-2-27b)
- In the Hugging Face "bonsai" listing, no id contained "227", while many contained "2-27" — [Hugging Face API](https://huggingface.co/api/models?search=bonsai&limit=100&sort=downloads)
- A Hugging Face search for "227b" returned 9 ids, all UUID or hash fragments that happen to contain the string (for example `ErrorAI/227bef2b-ed71-...`), none a 227B model — [Hugging Face API](https://huggingface.co/api/models?search=227b&limit=50)
- The official product name is "Bonsai 2 27B", with "2" the generation and "27B" the size — [PrismML docs](https://docs.prismml.com/models/bonsai-27b)
- A search for 227B-parameter open-weight LLMs found none; nearby 2026 sizes cited were Mistral Small 4 (119B), MiniMax MSA (~428B), Inkling (975B) and Kimi K2.7 Code (1T) — [FutureAGI](https://futureagi.com/blog/open-source-llm-releases/); [Context Studios](https://www.contextstudios.ai/guides/best-open-weight-llms-2026) (SEO-style guides, figures unverified against model cards)

### Inferences
- Ranked candidates for the origin of "227b":
  1. "Bonsai 2 27B" with the space dropped (high plausibility: exact character match, and it was the newest flagship, released about six weeks before the research date).
  2. Plain "Bonsai 27B" with a stray "2", or the two generations blended (moderate).
  3. Ternary "2-bit" packaging language, for example "27B mlx-2bit", merged into the name (low).
  4. "22.7B" or "2.27B" (low: no Bonsai size matches either; the actual sizes are 27B, 9B, 8B, 4B, 2B and 1.7B).
  5. A genuine 227B-parameter model (unsupported: PrismML's largest listed size is 27B).
- Reading "Bonsai 227b" as a 227-billion-parameter model would overstate the real model by about eight times.

### Gaps
- I could not trace where the user or their source first heard the name, so the mishearing hypothesis cannot be confirmed. The original source would settle it.
- I did not search Reddit, X or YouTube directly; the string could appear in social posts that web search does not index.

## Are there OpenAI models or codenames that could have been conflated?

### Takeaway
I found no OpenAI model or codename called Bonsai. OpenAI's real open-weight models are gpt-oss-120b and gpt-oss-20b, from August 2025, and their lowercase "b" naming may have contributed to the confusion, but no source shows that.

### Cited Findings
- OpenAI launched gpt-oss-120b and gpt-oss-20b on 2025-08-05 as open-weight models under Apache 2.0 — [OpenAI](https://openai.com/index/introducing-gpt-oss/?facet=app&mode=light) (older item)
- A search for an OpenAI "Bonsai" codename returned only gpt-oss coverage, none mentioning Bonsai — [Tom's Guide](https://www.tomsguide.com/ai/openai-launches-two-new-ai-models-ahead-of-gpt-5-heres-everything-you-need-to-know); [App Developer Magazine](https://appdevelopermagazine.com/openai-open-weight-models-released-for-optimized-laptop-performance/)
- An April 2026 review said OpenAI had published no follow-up (no gpt-oss-v2) — [AI Indigo](https://aiindigo.com/blog/gpt-oss-openai-review-the-shift-toward-open-weights-in-2026). This is a low-quality source and is about six months old.
- Conflicting dates exist: one page claims OpenAI released weights in May 2026 but appears to describe the 2025 models — [freeainews](https://freeainews.com/open-source/openai-gpt-oss-open-weight-2026/); contradicted by [OpenAI](https://openai.com/index/introducing-gpt-oss/?facet=app&mode=light)
- An aggregator mentions a gpt-oss-safeguard variant; I could not verify it officially — [noqta.tn](https://noqta.tn/en/blog/openai-gpt-oss-modeles-open-weight-guide-2026)
- Neither PrismML announcement mentions OpenAI — [PrismML](https://prismml.com/news/bonsai-2-27b); [PrismML press release](https://prismml.com/news/prismml-launches-bonsai-2-27b)
- MindStudio's test and DataCamp's overview also make no reference to OpenAI — [MindStudio](https://www.mindstudio.ai/blog/bonsai-2-27b-real-world-test); [DataCamp](https://www.datacamp.com/blog/bonsai-2-27b)
- Bonsai's local serving is described as OpenAI-compatible, which refers to the API format, not the company — [jangwook.net](https://jangwook.net/en/blog/en/prismml-bonsai-1bit-llm-edge-ai/); [OpenRouter](https://openrouter.ai/prism-ml)

### Inferences
- Plausible routes to the "OpenAI" attribution, none documented:
  - "OpenAI-compatible" in tutorials being read as "from OpenAI".
  - Lumping together locally run Apache-2.0 models, since gpt-oss and Bonsai share that licence and audience, plus lowercase "b" size suffixes.
  - General habit of attributing any prominent AI model to OpenAI.
- PrismML's named links are to Google and Samsung as backers, so attributing Bonsai to OpenAI runs against what the company itself states.

### Gaps
- OpenAI's model hub was not checked directly for October 2026, so an unannounced or very recent release cannot be excluded. Internal codenames are also inherently hard to rule out.
- No source directly discusses anyone confusing Bonsai with OpenAI.

## What are the distinguishing technical claims, and how well are they verified?

### Takeaway
PrismML's headline claim is near-lossless compression, 98.2% retention at about 9x smaller. It is vendor-reported, and what independent testing exists is less favourable. The Microsoft items rest on a peer-reviewed paper (tree classifier) or are product descriptions, and neither competes as an LLM.

### Cited Findings

**Bonsai 2 27B**
- Vendor claim: 83.9 aggregate versus 85.4 for Qwen3.8 27B (98.2%), more than 9x smaller, up to 143 tokens/s on an RTX 5090 and 46.8 on an M5 Max — [PrismML](https://prismml.com/news/bonsai-2-27b)
- Hands-on testing by MindStudio: vision and creative writing passed, but it missed a planted bug, a reset button stayed broken after three correction rounds, and translation looped on languages such as Tamil. The article notes its benchmark table reflects the vendor's claim and is not independently verified — [MindStudio](https://www.mindstudio.ai/blog/bonsai-2-27b-real-world-test). MindStudio is a commercial AI-tool vendor, and the test is anecdotal rather than a controlled benchmark.
- DataCamp reports a third-party knowledge-and-reasoning composite of about 79.9 versus 85.6 for FP16, without naming the reviewer, plus community reports of degradation past about 200K tokens — [DataCamp](https://www.datacamp.com/blog/bonsai-2-27b)
- Running Bonsai 2 needs PrismML's forks of llama.cpp and MLX for the low-bit kernels, per a secondary summary — [MindStudio](https://www.mindstudio.ai/blog/ternary-bonsai-2-27b-2bit-model); the docs say a `Q2_0` GGUF exists for upstream llama.cpp — [PrismML docs](https://docs.prismml.com/models/bonsai-27b)

**Source conflicts on Bonsai 2 27B**
- Benchmark base: 83.9 on a 20-benchmark aggregate per the [press release](https://prismml.com/news/prismml-launches-bonsai-2-27b), versus an 84.78 average across 14 benchmarks on the model card as reported by [MindStudio](https://www.mindstudio.ai/blog/bonsai-2-27b-real-world-test). Both are presented as 98.2%.
- Energy: 0.714 mWh/token on an RTX 4090 per [PrismML](https://prismml.com/news/bonsai-2-27b), versus 0.581 mWh/token attributed to PrismML by [DataCamp](https://www.datacamp.com/blog/bonsai-2-27b).
- Size: 5.9 GB headline versus 5.95, 7.21 and 8.60 GB by format — [PrismML docs](https://docs.prismml.com/models/bonsai-27b); a search summary also cited 6.70 GiB and 5.53 GiB GGUF packs without my confirming them.

**Bonsai 27B (first generation)**
- Vendor claim across 15 benchmarks: ternary retains 94.6%, 1-bit 89.5%. A 98-question community test put 1-bit at 82.9%, ternary at 86.2% and original Qwen3.6-27B at 94.2% — secondary write-up via [search on Bonsai 27B coverage](https://neurohive.io/en/state-of-the-art/h1-bonsai-27b-1-bit-weights-put-a-27b-parameter-model-on-a-smartphone-for-the-first-time-h1/). I did not open this page, and the summary did not make clear which of the returned articles carried these figures, so treat them as unconfirmed.

**1-bit Bonsai 8B**
- Claims: over 10x intelligence density, 14x smaller, 8x faster, 4-5x more energy efficient — [PrismML](https://prismml.com/news/prismml-launches-worlds-first-1-bit-ai-model)
- Qwen3 8B slightly leads on MMLU Redux, MuSR and GSM8K. "Intelligence density" is PrismML's own metric (1.06/GB versus 0.10/GB), and The Register did no independent testing — [The Register](https://www.theregister.com/2026/04/04/prismml_1bit_llm/)
- PrismML says the gains come mainly from reduced memory footprint, not from exploiting the 1-bit structure during inference — [search summary of PrismML](https://prismml.com/news/bonsai-8b)

**Microsoft Bonsai tree classifier (older)**
- Claims predictions in milliseconds on slow microcontrollers and accuracy up to 30% higher than other resource-efficient methods; published at ICML 2017 — [PMLR](https://proceedings.mlr.press/v70/kumar17a.html)

### Inferences
- PrismML's models are compressions of existing Qwen and FLUX.2 weights, not new pretrained foundation models, which is a useful fact for correcting a claim that this is an OpenAI model.
- The 98.2% figure is best treated as vendor-reported and unreplicated. Available third-party evidence points to retention below the vendor's figures, but its quality is limited.
- The first-generation 8B release has peer-reviewed status unknown: one Japanese-language write-up says a peer-reviewed paper probably does not exist, and I found no arXiv listing. PrismML does cite white papers.

### Gaps
- I did not read PrismML's whitepapers, so the benchmark list and methods are unexamined. I also did not resolve why 14 and 20 benchmark counts both appear; they may be different aggregates.
- I found no rigorous independent replication of Bonsai 2 27B from an established evaluation lab. The unnamed third-party figure in DataCamp could not be traced.
- r/LocalLLaMA threads were not reviewed directly, so community reception is known only through secondary blogs.
