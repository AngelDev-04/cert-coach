# AWS Certified AI Practitioner (AIF-C01) exam blueprint

> **Status:** researched 2026-09-09. Verified against the official AWS AIF-C01 Exam Guide and domain specifications.

## Purpose

This tool teaches and assesses official **AWS Certified AI Practitioner (AIF-C01)** exam coverage. It is not affiliated with AWS, does not reproduce live exam questions, and generates original practice material adhering strictly to the Question Presentation Contract and Privacy Contract.

## Official exam facts

- **Target role:** Practitioners across business, technical, and leadership functions seeking to demonstrate foundational knowledge of AI/ML and generative AI concepts and practical AWS AI service selection.
- **Target experience:** Foundational familiarity with AI/ML concepts and AWS Cloud services (no deep coding, mathematical proofs, or manual pipeline engineering required).
- **Question types:** Multiple choice (one best answer) and multiple response (two or more correct answers from five or more options).
- **Question count:** 65 questions (50 scored questions plus 15 unscored experimental questions).
- **Scoring scale:** 100–1,000; passing score is **700**.
- **Scoring rule:** Unanswered questions are scored incorrect; there is no penalty for guessing.

## Weighted domains

| ID | Domain Title | Official Weight | Official Task Statements |
| :--- | :--- | :---: | :--- |
| `fundamentals-ai-ml` | Fundamentals of AI and ML | **20%** | Basic concepts & terminology (1.1); Practical use cases (1.2); AI/ML development lifecycle (1.3) |
| `fundamentals-gen-ai` | Fundamentals of GenAI | **24%** | GenAI concepts & tokens (2.1); Business capabilities & limits (2.2); AWS GenAI infrastructure (2.3) |
| `foundation-models` | Applications of Foundation Models | **28%** | Design considerations & RAG (3.1); Prompt engineering (3.2); Training & fine-tuning (3.3); Model evaluation (3.4) |
| `responsible-ai` | Guidelines for Responsible AI | **14%** | Responsible AI development & bias (4.1); Transparent and explainable models (4.2) |
| `security-compliance-governance` | Security, Compliance, and Governance for AI Solutions | **14%** | Securing AI systems & prompt safety (5.1); Governance regulations & compliance (5.2) |

## Coverage map

### 1. Fundamentals of AI and ML (20%)
- **Terminology & Paradigms**: Artificial intelligence (AI), machine learning (ML), deep learning (DL), artificial neural networks, computer vision, natural language processing (NLP), large language models (LLMs), agentic AI.
- **Learning Approaches**: Supervised learning (labeled data, regression, classification), unsupervised learning (clustering, dimensionality reduction, anomaly detection), reinforcement learning (agents, environment, policy, reward signals).
- **Inference Types**: Real-time inferencing (low latency, interactive), batch inferencing (high throughput, scheduled offline), asynchronous inferencing (large payloads, queued), serverless inferencing (auto-scaling, intermittent traffic).
- **Data Modalities**: Tabular, time-series, text, image, audio, video; structured vs semi-structured vs unstructured.
- **AWS Managed AI Services**: Turn-key pre-trained APIs: Amazon Comprehend (NLP/sentiment), Amazon Transcribe (speech-to-text), Amazon Polly (text-to-speech), Amazon Translate (neural translation), Amazon Rekognition (vision/moderation), Amazon Textract (OCR/document extraction), Amazon Lex (conversational chatbots).
- **ML Lifecycle & MLOps**: Problem formulation, data ingestion/preparation, feature engineering, model training, hyperparameter tuning, model evaluation (accuracy, precision, recall, F1-score, confusion matrix, ROC-AUC), deployment, continuous monitoring (data drift, concept drift).

### 2. Fundamentals of Generative AI (24%)
- **Core GenAI Mechanics**: Transformer architecture, self-attention mechanism, tokens, context window size, embeddings, high-dimensional vector spaces, diffusion models.
- **Foundation Model Lifecycle**: Pre-training (web-scale unlabelled corpus), fine-tuning (task-specific labeled data), evaluation, alignment, deployment, inference economics.
- **Token Economics**: Pricing based on input (prompt) tokens and output (generation) tokens; prompt caching; cost trade-offs between model parameter sizes.
- **Agentic AI & MCP**: Autonomous agents combining foundation models with memory, planning, tools, and external APIs; Model Context Protocol (MCP) as standard for agent-to-tool integration.
- **Capabilities & Constraints**: Creative content synthesis, summarization, conversational assistants, code generation; constraints including hallucinations, nondeterminism, lack of factual grounding, and copyright/licensing exposure.
- **AWS Infrastructure**: Amazon Bedrock serverless API, Amazon SageMaker AI custom infrastructure, AWS Inferentia (cost-effective high-throughput inference chips), AWS Trainium (high-performance deep learning training chips), GPU instances.

### 3. Applications of Foundation Models (28%)
- **Selection Criteria**: Modality, reasoning ability, latency constraints, context window requirements, multilingual capability, cost per million tokens.
- **Inference Parameter Controls**: Temperature (randomness/creativity), Top-P (nucleus sampling probability mass), Top-K (candidate token pool size), maximum generation length, stop sequences.
- **Retrieval Augmented Generation (RAG)**: Architecture combining document retrieval with generative synthesis; chunking strategies, embedding generation, vector indexing, semantic search, citation generation, hallucination reduction.
- **AWS Vector Storage**: Amazon OpenSearch Service / OpenSearch Serverless, Amazon Aurora PostgreSQL with , Amazon RDS with , Amazon Neptune Analytics.
- **Prompt Engineering**: Zero-shot prompting, few-shot prompting (in-context examples), chain-of-thought (CoT) reasoning, system instructions, role assignment, negative prompts, Amazon Bedrock Prompt Management.
- **Customization Spectrum**: Prompt Engineering -> RAG -> Instruction Fine-Tuning -> Domain Adaptation / Continuous Pre-training -> Pre-training from scratch.
- **Evaluation & Benchmarks**: Human-in-the-loop review, automated NLP benchmarks (ROUGE, BLEU, BERTScore), LLM-as-a-judge, Amazon Bedrock Model Evaluation jobs.

### 4. Guidelines for Responsible AI (14%)
- **Pillars of Responsible AI**: Fairness, explainability, transparency, robustness, privacy, safety, veracity, inclusivity, governance.
- **Safety Controls**: Amazon Bedrock Guardrails (blocking harmful topics, content filters for hate/sexual/violence/insults, PII detection/masking, word/regex filters, contextual grounding checks).
- **Bias & Fairness**: Historical bias, representation bias, measurement bias; demographic parity; disparate impact analysis; balanced dataset curation.
- **Explainability & Transparency**: Black-box vs interpretable models; Amazon SageMaker Model Cards (documenting intended use, evaluation results, risk limitations); human-centered explanations and source citations.
- **Legal & Ethical Risks**: Intellectual property and copyright infringement, generated output liability, loss of customer trust, environmental/sustainability impact of model compute.

### 5. Security, Compliance, and Governance for AI Solutions (14%)
- **Data Protection & Encryption**: Data at rest encrypted with AWS KMS customer managed keys (CMKs); data in transit protected with TLS 1.3; private connectivity via AWS PrivateLink VPC endpoints for Bedrock and SageMaker.
- **AWS Privacy Guarantee**: Amazon Bedrock does NOT use customer prompts or completions to train base foundation models; customer data remains confined to the chosen AWS Region.
- **Access Control**: IAM least-privilege policies for model invocation, Amazon Bedrock AgentCore identity management, cross-account access controls.
- **Threat Mitigation**: Prompt injection defenses, jailbreak detection, model denial of service, training data poisoning, model extraction/inversion prevention.
- **Auditing & Compliance**: AWS CloudTrail (logging every API call), AWS Config (evaluating configuration compliance), AWS Artifact (on-demand SOC, ISO, HIPAA, PCI-DSS compliance reports), Generative AI Security Scoping Matrix.

## Authoritative source links

- [AWS Certified AI Practitioner (AIF-C01) Official Exam Guide](https://docs.aws.amazon.com/aws-certification/latest/ai-practitioner-01/ai-practitioner-01.html)
- [Domain 1: Fundamentals of AI and ML](https://docs.aws.amazon.com/aws-certification/latest/ai-practitioner-01/ai-practitioner-01-domain1.html)
- [Domain 2: Fundamentals of GenAI](https://docs.aws.amazon.com/aws-certification/latest/ai-practitioner-01/ai-practitioner-01-domain2.html)
- [Domain 3: Applications of Foundation Models](https://docs.aws.amazon.com/aws-certification/latest/ai-practitioner-01/ai-practitioner-01-domain3.html)
- [Domain 4: Guidelines for Responsible AI](https://docs.aws.amazon.com/aws-certification/latest/ai-practitioner-01/ai-practitioner-01-domain4.html)
- [Domain 5: Security, Compliance, and Governance](https://docs.aws.amazon.com/aws-certification/latest/ai-practitioner-01/ai-practitioner-01-domain5.html)
- [In-Scope AWS Services for AIF-C01](https://docs.aws.amazon.com/aws-certification/latest/ai-practitioner-01/aif-01-in-scope-services.html)
