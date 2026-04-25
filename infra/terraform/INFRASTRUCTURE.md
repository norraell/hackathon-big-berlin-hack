# Infrastructure Architecture

## Overview

This document describes the AWS infrastructure architecture for the AI Claims Intake System deployed using Terraform.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          Internet                                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   Route53 DNS   │
                    │  (Optional)     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   ACM Cert      │
                    │   (SSL/TLS)     │
                    └────────┬────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    Application Load Balancer                     │
│              (HTTP/HTTPS/WebSocket Support)                      │
│                  Public Subnets (Multi-AZ)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Target Group   │
                    └────────┬────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                       ECS Fargate Cluster                        │
│                   Private Subnets (Multi-AZ)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  ECS Task 1  │  │  ECS Task 2  │  │  ECS Task N  │         │
│  │  (Container) │  │  (Container) │  │  (Container) │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                 │
└────────────────────────────┼────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼────────┐    │    ┌────────▼────────┐
     │  RDS PostgreSQL │    │    │ ElastiCache     │
     │   (Multi-AZ)    │    │    │  Redis Cluster  │
     │ Private Subnets │    │    │ Private Subnets │
     └─────────────────┘    │    └─────────────────┘
                            │
                   ┌────────▼────────┐
                   │ Secrets Manager │
                   │  (Credentials)  │
                   └─────────────────┘
                            │
                   ┌────────▼────────┐
                   │   CloudWatch    │
                   │ Logs & Metrics  │
                   └─────────────────┘
```

## Components

### 1. Networking Layer

**VPC (Virtual Private Cloud)**
- CIDR: `10.0.0.0/16`
- Multi-AZ deployment across 2-3 availability zones
- Isolated network environment

**Public Subnets**
- Host Application Load Balancer
- NAT Gateways for outbound traffic
- Internet Gateway for inbound traffic

**Private Subnets**
- Host ECS tasks (application containers)
- Host RDS database
- Host ElastiCache Redis
- No direct internet access (via NAT Gateway)

**Security Groups**
- ALB Security Group: Allow HTTP (80) and HTTPS (443) from internet
- ECS Security Group: Allow traffic from ALB on port 8000
- RDS Security Group: Allow PostgreSQL (5432) from ECS
- Redis Security Group: Allow Redis (6379) from ECS

### 2. Compute Layer

**ECS Fargate**
- Serverless container orchestration
- No EC2 instance management
- Auto-scaling based on CPU/Memory
- Rolling deployments with circuit breaker

**Task Configuration**
- CPU: 1-2 vCPU (configurable)
- Memory: 2-4 GB (configurable)
- Container: Python FastAPI application
- Health checks on `/health` endpoint

**Auto Scaling**
- Target tracking on CPU (70%)
- Target tracking on Memory (80%)
- Min: 1-2 tasks
- Max: 10-20 tasks
- Scale-out: 60 seconds
- Scale-in: 300 seconds

### 3. Load Balancing

**Application Load Balancer**
- Layer 7 (HTTP/HTTPS) load balancing
- WebSocket support for Twilio Media Streams
- SSL/TLS termination
- Health checks every 30 seconds
- Connection draining: 30 seconds
- Sticky sessions for WebSocket connections

**Target Group**
- Protocol: HTTP
- Port: 8000
- Health check path: `/health`
- Healthy threshold: 2
- Unhealthy threshold: 3

### 4. Database Layer

**RDS PostgreSQL**
- Engine: PostgreSQL 16
- Instance class: db.t4g.micro to db.r6g.large
- Storage: 20-500 GB (auto-scaling)
- Multi-AZ for production
- Automated backups (7-30 days retention)
- Encryption at rest (AES-256)
- Enhanced monitoring
- Performance Insights

**Connection Pooling**
- Managed by application (SQLAlchemy)
- Max connections: Based on instance class
- Connection timeout: 30 seconds

### 5. Cache Layer

**ElastiCache Redis**
- Engine: Redis 7.x
- Node type: cache.t4g.micro to cache.r6g.large
- Cluster mode: Disabled (single shard)
- Multi-AZ with automatic failover (production)
- Encryption in-transit (TLS)
- Encryption at-rest
- Auth token enabled
- Automated snapshots (5 days retention)

**Use Cases**
- Session state management
- Call state tracking
- Temporary data caching
- Rate limiting

### 6. Storage Layer

**ECR (Elastic Container Registry)**
- Private Docker image repository
- Image scanning on push
- Lifecycle policies (keep last 10 tagged images)
- Encryption at rest

**S3 Buckets**
- ALB access logs
- Application backups (optional)
- Lifecycle policies for cost optimization

### 7. Security Layer

**Secrets Manager**
- Encrypted credential storage
- Automatic rotation support
- Version management
- IAM-based access control

**Stored Secrets:**
- Database credentials
- Redis auth token
- Twilio credentials
- AI service API keys
- Application secret key

**IAM Roles**
- ECS Task Execution Role: Pull images, read secrets
- ECS Task Role: Application permissions
- RDS Monitoring Role: Enhanced monitoring

### 8. Monitoring Layer

**CloudWatch Logs**
- Centralized log aggregation
- Log groups per service
- Retention: 7-90 days
- Log insights for querying

**CloudWatch Metrics**
- ECS: CPU, Memory, Task count
- ALB: Request count, Response time, Error rate
- RDS: CPU, Connections, Storage
- Redis: CPU, Memory, Evictions
- Custom application metrics

**CloudWatch Alarms**
- High CPU utilization (>80%)
- High memory utilization (>85%)
- High response time (>1500ms)
- Error rate threshold
- Database connection issues
- Unhealthy targets

**CloudWatch Dashboard**
- Real-time metrics visualization
- Service health overview
- Performance trends
- Error tracking

### 9. DNS and SSL

**Route53 (Optional)**
- DNS management
- Health checks
- Failover routing

**ACM (AWS Certificate Manager)**
- Free SSL/TLS certificates
- Automatic renewal
- Domain validation

## Data Flow

### Incoming Call Flow

1. **Call Initiation**
   - User calls Twilio phone number
   - Twilio sends webhook to ALB
   - ALB routes to healthy ECS task

2. **WebSocket Connection**
   - Twilio establishes Media Stream WebSocket
   - ALB maintains sticky session
   - ECS task handles bidirectional audio

3. **Audio Processing**
   - Receive μ-law audio from Twilio
   - Convert to PCM for STT (Gemini)
   - Process with LLM (Gemini)
   - Generate speech with TTS (Gradium)
   - Convert back to μ-law for Twilio

4. **State Management**
   - Session state stored in Redis
   - Dialog state machine progression
   - Transcript buffering

5. **Data Persistence**
   - Claim data saved to PostgreSQL
   - Transcripts stored with retention policy
   - Audit logs in CloudWatch

## High Availability

### Multi-AZ Deployment

**Application Tier**
- ECS tasks distributed across AZs
- ALB spans multiple AZs
- Automatic failover

**Database Tier**
- RDS Multi-AZ with synchronous replication
- Automatic failover (1-2 minutes)
- Redis Multi-AZ with automatic failover

**Network Tier**
- NAT Gateways in each AZ
- Multiple subnets per tier

### Disaster Recovery

**RTO (Recovery Time Objective): 15 minutes**
- Automated failover for RDS and Redis
- ECS tasks auto-restart on failure
- ALB health checks detect issues

**RPO (Recovery Point Objective): 5 minutes**
- Continuous RDS replication
- Redis snapshots every 5 minutes
- Transaction logs for point-in-time recovery

## Scalability

### Horizontal Scaling

**Application**
- Auto-scaling from 1 to 20 tasks
- Scale based on CPU/Memory metrics
- Handles 100+ concurrent calls

**Database**
- Read replicas (optional)
- Connection pooling
- Query optimization

**Cache**
- Redis cluster mode (optional)
- Sharding for large datasets

### Vertical Scaling

**Application**
- Increase task CPU/Memory
- No downtime (rolling update)

**Database**
- Increase instance class
- Minimal downtime (Multi-AZ)

**Cache**
- Increase node type
- Minimal downtime (Multi-AZ)

## Cost Optimization

### Development Environment
- Single AZ deployment
- Smaller instance sizes
- Reduced backup retention
- FARGATE_SPOT for cost savings
- **Estimated: $150-200/month**

### Production Environment
- Multi-AZ deployment
- Larger instance sizes
- Extended backup retention
- Reserved instances (optional)
- **Estimated: $500-800/month**

### Cost Breakdown
- ECS Fargate: 30-40%
- NAT Gateway: 25-30%
- RDS: 15-20%
- ALB: 10-15%
- ElastiCache: 8-12%
- Other (CloudWatch, S3, etc.): 5-10%

## Security Best Practices

1. **Network Security**
   - Private subnets for sensitive resources
   - Security groups with least privilege
   - VPC Flow Logs enabled

2. **Data Security**
   - Encryption at rest (RDS, Redis, S3)
   - Encryption in transit (TLS/SSL)
   - Secrets in Secrets Manager

3. **Access Control**
   - IAM roles with least privilege
   - No hardcoded credentials
   - MFA for AWS console access

4. **Monitoring**
   - CloudWatch alarms for anomalies
   - CloudTrail for audit logs
   - GuardDuty for threat detection

5. **Compliance**
   - GDPR-compliant data handling
   - PII encryption
   - Data retention policies

## Maintenance Windows

**Recommended Schedule:**
- Database maintenance: Monday 3:00-5:00 AM UTC
- Redis maintenance: Monday 5:00-7:00 AM UTC
- Application updates: Rolling, no downtime

## Backup Strategy

**Automated Backups:**
- RDS: Daily snapshots, 7-30 days retention
- Redis: Snapshots every 5 minutes, 5 days retention
- Terraform state: S3 with versioning

**Manual Backups:**
- Before major changes
- Before version upgrades
- Monthly full backups

## Performance Targets

- **Response Time**: p95 < 1500ms
- **Availability**: 99.9% uptime
- **Error Rate**: < 0.1%
- **Concurrent Calls**: 100+
- **Database Connections**: < 80% of max

## References

- [Terraform Configuration](.)
- [Deployment Guide](../../DEPLOYMENT.md)
- [Quick Reference](QUICK_REFERENCE.md)
- [Application Architecture](../../architecture.md)