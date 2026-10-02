"""Exam registry providing catalog data, blueprints, and rubrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cert_coach.core.config import TEMPLATES_DIR
from cert_coach.core.models import ExamMetadata, ExamType


CLF_C02_CATALOG: dict[str, Any] = {
    "schema_version": "1.0",
    "exam_code": "CLF-C02",
    "exam_title": "AWS Certified Cloud Practitioner",
    "passing_score": 700,
    "scale_max": 1000,
    "domains": [
        {
            "id": "cloud-concepts",
            "name": "Cloud Concepts",
            "weight": 24,
            "official_reference": "AWS CLF-C02 Exam Guide Domain 1",
            "tasks": [
                {
                    "id": "1.1",
                    "title": "Define the benefits of the AWS Cloud",
                    "selection_rules": ["Identify high availability, elasticity, agility, global reach"],
                    "common_confusions": ["Confusing elasticity with scalability"],
                    "topics": [
                        {"id": "aws-cloud-value", "name": "AWS Cloud Value Proposition"},
                        {"id": "cloud-economics", "name": "Cloud Economics & TCO"},
                    ],
                },
                {
                    "id": "1.2",
                    "title": "Identify design principles of the AWS Cloud",
                    "selection_rules": ["Apply Well-Architected Framework foundational principles"],
                    "common_confusions": ["Confusing Capex vs Opex principles"],
                    "topics": [
                        {"id": "well-architected-foundations", "name": "Well-Architected Foundations"}
                    ],
                },
            ],
        },
        {
            "id": "security-compliance",
            "name": "Security and Compliance",
            "weight": 30,
            "official_reference": "AWS CLF-C02 Exam Guide Domain 2",
            "tasks": [
                {
                    "id": "2.1",
                    "title": "Understand the AWS Shared Responsibility Model",
                    "selection_rules": ["Distinguish customer responsibility from AWS responsibility"],
                    "common_confusions": ["Assuming customer manages physical data center security"],
                    "topics": [
                        {"id": "shared-responsibility-model", "name": "Shared Responsibility Model"},
                        {"id": "iam-fundamentals", "name": "IAM Users, Groups, Roles & Policies"},
                    ],
                },
                {
                    "id": "2.2",
                    "title": "Understand AWS Cloud security and governance concepts",
                    "selection_rules": ["Apply encryption in transit and at rest basics"],
                    "common_confusions": ["Confusing Security Groups with NACLs"],
                    "topics": [
                        {"id": "aws-security-services", "name": "AWS Security Services (Shield, WAF, GuardDuty)"}
                    ],
                },
            ],
        },
        {
            "id": "cloud-technology",
            "name": "Cloud Technology and Services",
            "weight": 34,
            "official_reference": "AWS CLF-C02 Exam Guide Domain 3",
            "tasks": [
                {
                    "id": "3.1",
                    "title": "Define methods of deploying and operating in the AWS Cloud",
                    "selection_rules": ["Distinguish console, CLI, SDK, and IaC (CloudFormation)"],
                    "common_confusions": ["CLI vs SDK operational contexts"],
                    "topics": [
                        {"id": "aws-management-interfaces", "name": "Management Console, CLI, SDK"},
                    ],
                },
                {
                    "id": "3.2",
                    "title": "Define the AWS global infrastructure",
                    "selection_rules": ["Identify Regions, Availability Zones, and Edge Locations"],
                    "common_confusions": ["Assuming AZs are single data centers"],
                    "topics": [
                        {"id": "global-infrastructure", "name": "Regions, AZs, Edge Locations"},
                    ],
                },
                {
                    "id": "3.3",
                    "title": "Identify core AWS compute, storage, and database services",
                    "selection_rules": ["EC2, Lambda, ECS, S3, EBS, RDS, DynamoDB use-cases"],
                    "common_confusions": ["EBS vs S3 storage models"],
                    "topics": [
                        {"id": "core-compute", "name": "EC2, Lambda, Containers"},
                        {"id": "core-storage", "name": "S3, EBS, EFS"},
                        {"id": "core-databases", "name": "RDS, DynamoDB, Aurora"},
                    ],
                },
            ],
        },
        {
            "id": "billing-pricing",
            "name": "Billing, Pricing, and Support",
            "weight": 12,
            "official_reference": "AWS CLF-C02 Exam Guide Domain 4",
            "tasks": [
                {
                    "id": "4.1",
                    "title": "Compare AWS pricing models",
                    "selection_rules": ["On-Demand, Reserved Instances, Savings Plans, Spot"],
                    "common_confusions": ["Savings Plans vs Reserved Instances flexibility"],
                    "topics": [
                        {"id": "pricing-models", "name": "On-Demand, Reserved, Spot, Savings Plans"},
                    ],
                },
                {
                    "id": "4.2",
                    "title": "Understand billing, cost management, and support plans",
                    "selection_rules": ["Cost Explorer, Budgets, AWS Support Plan tiers"],
                    "common_confusions": ["Basic vs Developer vs Business support SLAs"],
                    "topics": [
                        {"id": "cost-tools-and-support", "name": "Cost Explorer, Budgets, Support Tiers"},
                    ],
                },
            ],
        },
    ],
}


AIF_C01_CATALOG: dict[str, Any] = {
    "schema_version": "1.0",
    "exam_code": "AIF-C01",
    "exam_title": "AWS Certified AI Practitioner",
    "passing_score": 700,
    "scale_max": 1000,
    "domains": [
        {
            "id": "fundamentals-ai-ml",
            "name": "Fundamentals of AI and ML",
            "weight": 20,
            "official_reference": "AWS AIF-C01 Exam Guide Domain 1",
            "tasks": [
                {
                    "id": "1.1",
                    "title": "Explain basic AI, ML, and deep learning concepts",
                    "selection_rules": ["Supervised vs unsupervised vs reinforcement learning"],
                    "common_confusions": ["Overfitting vs underfitting trade-offs"],
                    "topics": [
                        {"id": "ai-ml-basics", "name": "AI/ML/DL Concepts & Types"},
                        {"id": "ml-lifecycle", "name": "Data prep, training, tuning, inference"},
                    ],
                }
            ],
        },
        {
            "id": "fundamentals-gen-ai",
            "name": "Fundamentals of Generative AI",
            "weight": 24,
            "official_reference": "AWS AIF-C01 Exam Guide Domain 2",
            "tasks": [
                {
                    "id": "2.1",
                    "title": "Explain generative AI concepts and capabilities",
                    "selection_rules": ["Transformers, tokens, embeddings, hallucination risks"],
                    "common_confusions": ["Deterministic algorithms vs probabilistic generative models"],
                    "topics": [
                        {"id": "gen-ai-concepts", "name": "LLMs, Diffusion Models, Tokens & Context Window"},
                        {"id": "prompt-engineering", "name": "Zero-shot, Few-shot, Chain-of-Thought"},
                    ],
                }
            ],
        },
        {
            "id": "foundation-models",
            "name": "Applications of Foundation Models",
            "weight": 28,
            "official_reference": "AWS AIF-C01 Exam Guide Domain 3",
            "tasks": [
                {
                    "id": "3.1",
                    "title": "Select appropriate foundation models and AWS AI services",
                    "selection_rules": ["Amazon Bedrock model selection, Amazon SageMaker JumpStart"],
                    "common_confusions": ["Fine-tuning vs RAG trade-offs"],
                    "topics": [
                        {"id": "amazon-bedrock", "name": "Amazon Bedrock & Model Evaluation"},
                        {"id": "rag-architectures", "name": "Retrieval Augmented Generation (RAG) & Vector Stores"},
                    ],
                }
            ],
        },
        {
            "id": "responsible-ai",
            "name": "Guidelines for Responsible AI",
            "weight": 14,
            "official_reference": "AWS AIF-C01 Exam Guide Domain 4",
            "tasks": [
                {
                    "id": "4.1",
                    "title": "Identify responsible AI principles and practices",
                    "selection_rules": ["Fairness, transparency, explainability, safety, privacy"],
                    "common_confusions": ["Bias mitigation vs post-hoc explanation"],
                    "topics": [
                        {"id": "responsible-ai-principles", "name": "Fairness, Explainability, Safety & Guardrails"}
                    ],
                }
            ],
        },
        {
            "id": "security-governance",
            "name": "Security, Compliance, and Governance for AI Solutions",
            "weight": 14,
            "official_reference": "AWS AIF-C01 Exam Guide Domain 5",
            "tasks": [
                {
                    "id": "5.1",
                    "title": "Implement security and data privacy controls for AI",
                    "selection_rules": ["Bedrock data protection, IAM policies for models, VPC endpoints"],
                    "common_confusions": ["Data retention policies with external vs AWS foundation models"],
                    "topics": [
                        {"id": "ai-data-security", "name": "Bedrock Guardrails, Encryption, Compliance"}
                    ],
                }
            ],
        },
    ],
}


class ExamRegistry:
    """Provides exam metadata, blueprints, and concept catalogs."""

    METADATA: dict[str, ExamMetadata] = {
        ExamType.SAA_C03.value: ExamMetadata(
            code="SAA-C03",
            name="AWS Certified Solutions Architect - Associate",
            description="High availability, security, resilience, performance, and cost optimization",
            domains_count=4,
            tasks_count=14,
            status="active",
        ),
        ExamType.CLF_C02.value: ExamMetadata(
            code="CLF-C02",
            name="AWS Certified Cloud Practitioner",
            description="Foundational cloud concepts, core AWS services, security, pricing, and support",
            domains_count=4,
            tasks_count=19,
            status="active",
        ),
        ExamType.AIF_C01.value: ExamMetadata(
            code="AIF-C01",
            name="AWS Certified AI Practitioner",
            description="Fundamentals of AI/ML, Generative AI, Foundation Models, and Responsible AI",
            domains_count=5,
            tasks_count=14,
            status="active",
        ),
    }

    @classmethod
    def list_exams(cls) -> list[ExamMetadata]:
        return list(cls.METADATA.values())

    @classmethod
    def get_metadata(cls, exam: str | ExamType) -> ExamMetadata:
        key = exam.value if isinstance(exam, ExamType) else str(exam).lower()
        if key not in cls.METADATA:
            valid = ", ".join(cls.METADATA.keys())
            raise ValueError(f"Unknown exam '{exam}'. Supported: {valid}")
        return cls.METADATA[key]

    @classmethod
    def get_catalog(cls, exam: str | ExamType) -> dict[str, Any]:
        meta = cls.get_metadata(exam)
        catalog_file = TEMPLATES_DIR / "docs" / f"{meta.code.lower()}-concept-catalog.json"
        if catalog_file.is_file():
            with catalog_file.open(encoding="utf-8") as f:
                return json.load(f)
        key = exam.value if isinstance(exam, ExamType) else str(exam).lower()
        if key == ExamType.CLF_C02.value:
            return CLF_C02_CATALOG
        if key == ExamType.AIF_C01.value:
            return AIF_C01_CATALOG
        raise FileNotFoundError(f"{meta.code} catalog file not found: {catalog_file}")

    @classmethod
    def get_blueprint_markdown(cls, exam: str | ExamType) -> str:
        meta = cls.get_metadata(exam)
        blueprint_file = TEMPLATES_DIR / "docs" / f"{meta.code.lower()}-exam-blueprint.md"
        if blueprint_file.is_file():
            return blueprint_file.read_text(encoding="utf-8")
        catalog = cls.get_catalog(exam)
        lines = [
            f"# {meta.code} Exam Blueprint Summary",
            "",
            f"**Exam Title:** {meta.name} ({meta.code})  ",
            f"**Passing Score:** {catalog.get('passing_score', 700)} / {catalog.get('scale_max', 1000)}  ",
            "",
            "## Domain Weight Distribution",
            "",
            "| Domain ID | Domain Title | Official Weight | Tasks |",
            "| :--- | :--- | :---: | :---: |",
        ]
        for d in catalog.get("domains", []):
            task_count = len(d.get("tasks", []))
            lines.append(f"| `{d['id']}` | {d['name']} | **{d['weight']}%** | {task_count} tasks |")
        lines.append("")
        return "\n".join(lines)
