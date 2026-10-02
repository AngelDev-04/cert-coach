# AWS Certified Solutions Architect - Associate (SAA-C03) exam blueprint

> **Status:** researched 2026-08-28. Recheck the official AWS guide before publishing a new Power version or treating this as current exam policy.

## Purpose

This Power teaches and assesses the official **AWS Certified Solutions Architect - Associate (SAA-C03)** coverage. It is not affiliated with AWS, does not reproduce live exam questions, and must create original practice questions only.

## Official exam facts

- Target role: solutions architect; AWS describes the target candidate as having at least one year of hands-on experience designing AWS cloud solutions.
- The exam validates designs aligned to the AWS Well-Architected Framework and the ability to design for current and future needs, improve existing solutions, and balance security, resilience, performance, and cost.
- Question types: multiple choice (one best answer) and multiple response (two or more correct answers).
- Scoring: 50 scored questions, plus 15 unscored questions that are not identified during the exam.
- Scale: 100–1,000; current published passing score: 720.
- Unanswered questions are incorrect; there is no guessing penalty.

## Weighted domains

| ID | Domain | Weight | Official task statements |
| --- | --- | ---: | --- |
| `secure` | Design Secure Architectures | 30% | Secure access; secure workloads and applications; data security controls |
| `resilient` | Design Resilient Architectures | 26% | Scalable/loosely coupled architectures; highly available/fault-tolerant architectures |
| `high-performing` | Design High-Performing Architectures | 24% | Storage; compute; databases; networks; data ingestion/transformation |
| `cost-optimized` | Design Cost-Optimized Architectures | 20% | Storage; compute; databases; networks |

Use the domain weights when proposing a study plan or a representative mock-quiz mix. Do not claim that a short practice quiz duplicates the real exam distribution exactly.

## Coverage map

### 1. Secure architectures (30%)

- IAM users, groups, roles, policies, STS, least privilege, MFA, federation, IAM Identity Center, cross-account access, AWS Organizations, Control Tower, and SCPs.
- VPC security: security groups, network ACLs, routing, NAT gateways, public/private segmentation, VPN and Direct Connect.
- Workload protection: Secrets Manager, Cognito, WAF, Shield, GuardDuty, Macie, application credentials, endpoints, ports/protocols, and external threats.
- Data protection: KMS, key policies, encryption at rest and in transit, ACM/TLS, backup/replication, data governance/classification/retention/lifecycle, certificate renewal, and compliance controls.

### 2. Resilient architectures (26%)

- Loose coupling and scalable designs: APIs, event-driven architectures, queues/pub-sub, microservices, multi-tier applications, containers, serverless, caching, load balancing, workflow orchestration, and read replicas.
- Availability and fault tolerance: multi-AZ/multi-Region patterns, Route 53/failover, removal of single points of failure, durable storage, backups, automation, immutable infrastructure, proxies, quotas/throttling, observability, and legacy workload reliability.
- Disaster recovery: backup and restore, pilot light, warm standby, active-active; select by stated RTO/RPO and business requirement.

### 3. High-performing architectures (24%)

- Storage: select and scale S3, EBS, EFS, and hybrid storage for performance and future demand.
- Compute: EC2 sizing, Auto Scaling, Lambda sizing, ECS/EKS/Fargate, Batch/EMR, decoupling, queueing and messaging, metrics-driven scaling, and distributed/edge computation.
- Databases: access patterns, relational/non-relational/in-memory choices, Aurora/DynamoDB, capacity, connections/proxies, caching/ElastiCache, read replicas, engine selection, and migrations.
- Networks: multi-tier/global/hybrid topology, IP addressing/subnets/routing, ALB/NLB selection, CloudFront/Global Accelerator, VPN/Direct Connect/PrivateLink, placement, and scalability.
- Data: data lakes, ingestion frequency/configuration, Kinesis streaming, DataSync/Storage Gateway transfer, Glue transformation, EMR processing, Athena/Lake Formation/QuickSight analytics and visualization, and CSV-to-Parquet conversion.

### 4. Cost-optimized architectures (20%)

- Storage: service/tier/lifecycle selection, S3 lifecycle, EBS volume type, backup/archive, access patterns, migration/transfer, capacity, hybrid storage, and cost-management tools.
- Compute: EC2 family/size, Lambda/EC2/Fargate selection, horizontal/vertical scale, Auto Scaling, hibernation, Spot Instances, Reserved Instances, Savings Plans, production vs non-production availability, and load balancing.
- Databases: cost-effective database engine/type/service, capacity, backups/retention, caching, replication, connections/proxies, data retention, and migrations.
- Networks: NAT cost trade-offs, VPC peering/Transit Gateway, VPN/Direct Connect/internet decisions, data-transfer cost routes, VPC endpoints, CDN/edge caching, bandwidth, throttling, and cost management.

## Authoritative source links

- [SAA-C03 official exam guide](https://docs.aws.amazon.com/aws-certification/latest/solutions-architect-associate-03/solutions-architect-associate-03.html)
- [Domain 1: Secure](https://docs.aws.amazon.com/aws-certification/latest/solutions-architect-associate-03/solutions-architect-associate-03-domain1.html)
- [Domain 2: Resilient](https://docs.aws.amazon.com/aws-certification/latest/solutions-architect-associate-03/solutions-architect-associate-03-domain2.html)
- [Domain 3: High-Performing](https://docs.aws.amazon.com/aws-certification/latest/solutions-architect-associate-03/solutions-architect-associate-03-domain3.html)
- [Domain 4: Cost-Optimized](https://docs.aws.amazon.com/aws-certification/latest/solutions-architect-associate-03/solutions-architect-associate-03-domain4.html)
