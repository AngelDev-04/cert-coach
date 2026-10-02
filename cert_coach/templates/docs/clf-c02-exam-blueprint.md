# AWS Certified Cloud Practitioner (CLF-C02) exam blueprint

> **Status:** researched 2026-09-09. Verified against the official AWS CLF-C02 Exam Guide and domain specifications.

## Purpose

This tool teaches and assesses official **AWS Certified Cloud Practitioner (CLF-C02)** exam coverage. It is not affiliated with AWS, does not reproduce live exam questions, and generates original practice material adhering strictly to the Question Presentation Contract and Privacy Contract.

## Official exam facts

- **Target role:** Individuals demonstrating overall foundational knowledge of the AWS Cloud, independent of specific technical or engineering job roles.
- **Target experience:** Foundational understanding of cloud concepts, security, technology, billing, and pricing models.
- **Question types:** Multiple choice (one correct option from four choices) and multiple response (two or more correct options from five or more choices).
- **Question count:** 65 questions (50 scored questions plus 15 unscored experimental questions).
- **Scoring scale:** 100–1,000; passing score is **700**.
- **Scoring rule:** Unanswered questions are scored incorrect; there is no penalty for guessing.

## Weighted domains

| ID | Domain Title | Official Weight | Official Task Statements |
| :--- | :--- | :---: | :--- |
| `cloud-concepts` | Cloud Concepts | **24%** | Benefits of AWS Cloud (1.1); Design principles (1.2); Migration benefits & strategies (1.3); Cloud economics (1.4) |
| `security-compliance` | Security and Compliance | **30%** | Shared responsibility model (2.1); Security, governance & compliance (2.2); Access management & IAM (2.3); Security components & resources (2.4) |
| `cloud-technology` | Cloud Technology and Services | **34%** | Deployment methods & models (3.1); Global infrastructure (3.2); Compute services (3.3); Database services (3.4); Network services (3.5); Storage services (3.6); AI/ML & analytics (3.7); Other services (3.8) |
| `billing-pricing` | Billing, Pricing, and Support | **12%** | Pricing models (4.1); Billing, budget & cost tools (4.2); Technical resources & Support tiers (4.3) |

## Coverage map

### 1. Cloud Concepts (24%)
- **Value Proposition**: Scalability, elasticity, high availability, agility, global deployment speed, fault tolerance.
- **AWS Well-Architected Framework**: 6 Pillars (Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization, Sustainability) and core design principles.
- **AWS Cloud Adoption Framework (AWS CAF)**: 6 Perspectives (Business, People, Governance, Platform, Security, Operations).
- **Migration Strategies (7 Rs)**: Rehost (lift-and-shift), Replatform (lift-tinker-and-shift), Repurchase (drop-and-shop to SaaS), Refactor/Re-architect (cloud-native), Retain, Retire, Relocate.
- **Cloud Economics**: CapEx (upfront hardware expenditure) vs OpEx (pay-as-you-go operating expense); economies of scale; rightsizing; BYOL vs license-included.

### 2. Security and Compliance (30%)
- **AWS Shared Responsibility Model**: AWS responsible for Security OF the cloud (physical datacenters, hardware, virtualization layer, network facilities); Customer responsible for Security IN the cloud (customer data, IAM credentials, OS patching on EC2, firewall rules, encryption). Shifts across IaaS (EC2), PaaS (RDS), and Serverless (Lambda).
- **Compliance & Governance**: AWS Artifact (on-demand SOC, PCI-DSS, ISO audit reports and compliance agreements), compliance programs across industries and geographies.
- **Security Monitoring Services**: Amazon GuardDuty (intelligent threat detection via DNS, VPC flow, and CloudTrail logs), Amazon Inspector (automated vulnerability scanning of EC2 instances and container images), AWS Security Hub (centralized posture management), AWS Shield (DDoS protection).
- **IAM & Access Control**: Root user protection (delete access keys, enable MFA, avoid daily use); IAM users, groups, customer managed policies, AWS managed policies; IAM roles (temporary credentials for services/applications); Principle of least privilege; AWS IAM Identity Center (centralized SSO and multi-account identity federation).
- **Perimeter Security**: AWS WAF (Layer 7 web application firewall blocking SQLi, XSS), AWS Shield Standard vs Advanced, AWS Firewall Manager, Security Groups (stateful instance firewalls) vs Network ACLs (stateless subnet firewalls).

### 3. Cloud Technology and Services (34%)
- **Deployment & Management**: AWS Management Console, AWS CLI, AWS SDKs, Infrastructure as Code via AWS CloudFormation; deployment models (All-in Cloud, Hybrid, On-Premises).
- **AWS Global Infrastructure**: AWS Regions (geographically isolated areas), Availability Zones (AZs - discrete datacenters with redundant power/networking), Edge Locations (caching content for Amazon CloudFront and Route 53); multi-AZ resilience vs multi-Region disaster recovery.
- **Compute Services**: Amazon EC2 (instance families: General Purpose, Compute Optimized, Memory Optimized, Storage Optimized, Accelerated Computing); container orchestration (Amazon ECS, Amazon EKS, AWS Fargate); serverless compute (AWS Lambda); Elastic Load Balancing (ALB, NLB, GLB) paired with EC2 Auto Scaling for elasticity.
- **Database Services**: Relational (Amazon RDS for MySQL, PostgreSQL, MariaDB, Oracle, SQL Server; Amazon Aurora for high-performance cloud-native MySQL/PostgreSQL); NoSQL (Amazon DynamoDB); in-memory caching (Amazon ElastiCache, MemoryDB); database migration (AWS DMS, AWS SCT).
- **Networking Services**: Amazon VPC (subnets, route tables, Internet Gateways, NAT Gateways, VPC peering); Amazon Route 53 (DNS resolution and traffic routing); AWS Site-to-Site VPN; AWS Direct Connect (dedicated private fiber connection).
- **Storage Services**: Amazon S3 (Standard, Intelligent-Tiering, Standard-IA, One Zone-IA, Glacier Instant Retrieval, Glacier Flexible Retrieval, Glacier Deep Archive; Lifecycle policies); Amazon EBS (persistent block storage for EC2); EC2 Instance Store (ephemeral temporary storage); Amazon EFS (shared POSIX Linux network file storage); Amazon FSx (specialized Windows/Lustre filesystems); AWS Storage Gateway (hybrid cloud storage); AWS Backup (centralized automated backups).
- **AI/ML & Analytics**: Pre-trained managed AI (Amazon Rekognition, Polly, Transcribe, Translate, Lex, Comprehend); Amazon Bedrock (serverless foundation models); Amazon SageMaker AI (end-to-end ML platform); Analytics (Amazon Athena for serverless S3 SQL queries, AWS Glue for ETL, Amazon EMR for big data clusters, Amazon Kinesis for streaming, Amazon QuickSight for business intelligence).
- **Application Integration & Developer Tools**: Amazon SQS (decoupled message queues), Amazon SNS (pub/sub notifications), Amazon EventBridge (event routing), AWS Step Functions (workflow orchestration); developer tools (AWS CodePipeline, AWS CodeBuild, AWS X-Ray); end-user computing (Amazon WorkSpaces, Amazon AppStream 2.0); AWS IoT Core.

### 4. Billing, Pricing, and Support (12%)
- **Pricing & Purchasing Models**: On-Demand (flexible pay-as-you-go), Reserved Instances (1 or 3-year commitment for predictable workloads), Savings Plans (Compute Savings Plans and EC2 Instance Savings Plans), Spot Instances (spare capacity up to 90% discount for fault-tolerant batch workloads), Dedicated Hosts and Dedicated Instances.
- **Cost Transfer & Storage Costs**: Free inbound data transfer; outbound egress costs across Regions or to the internet; S3 storage tier costs and retrieval fees.
- **Billing & Cost Management Tools**: AWS Pricing Calculator (pre-deployment cost estimation), AWS Cost Explorer (historical visual spend analysis and forecasting), AWS Budgets (proactive spend/usage threshold alerts via SNS/email), AWS Cost and Usage Report (CUR - granular hourly/daily usage data); AWS Organizations consolidated billing and volume discount tiers; Cost allocation tags.
- **AWS Support Plans**:
  - *Basic Support*: Included for all accounts, 24x7 customer service, documentation, 7 core Trusted Advisor checks.
  - *Developer Support*: Business-hours email access to support associates, 1 primary contact, <12 hr general guidance SLA.
  - *Business Support*: 24x7 phone, chat, email access to Cloud Support Engineers, unlimited contacts, <1 hr production down SLA, full Trusted Advisor checks.
  - *Enterprise On-Ramp Support*: 24x7 phone/chat/email access, <30 min production system impaired SLA, pool of Technical Account Managers (TAMs).
  - *Enterprise Support*: 24x7 access, <15 min business-critical system down SLA, designated Technical Account Manager (TAM), Concierge support, Infrastructure Event Management (IEM).
- **Advisory & Community Resources**: AWS Trusted Advisor (cost optimization, security, fault tolerance, performance, service quotas), AWS Health Dashboard (account-specific operational alerts), AWS Knowledge Center, AWS re:Post, AWS Partner Network (APN), and AWS Marketplace.

## Authoritative source links

- [AWS Certified Cloud Practitioner (CLF-C02) Official Exam Guide](https://docs.aws.amazon.com/aws-certification/latest/cloud-practitioner-02/cloud-practitioner-02.html)
- [Domain 1: Cloud Concepts](https://docs.aws.amazon.com/aws-certification/latest/cloud-practitioner-02/cloud-practitioner-02-domain1.html)
- [Domain 2: Security and Compliance](https://docs.aws.amazon.com/aws-certification/latest/cloud-practitioner-02/cloud-practitioner-02-domain2.html)
- [Domain 3: Cloud Technology and Services](https://docs.aws.amazon.com/aws-certification/latest/cloud-practitioner-02/cloud-practitioner-02-domain3.html)
- [Domain 4: Billing, Pricing, and Support](https://docs.aws.amazon.com/aws-certification/latest/cloud-practitioner-02/cloud-practitioner-02-domain4.html)
- [In-Scope AWS Services for CLF-C02](https://docs.aws.amazon.com/aws-certification/latest/cloud-practitioner-02/clf-02-in-scope-services.html)
- [Technologies and Concepts for CLF-C02](https://docs.aws.amazon.com/aws-certification/latest/cloud-practitioner-02/clf-technologies-concepts.html)
