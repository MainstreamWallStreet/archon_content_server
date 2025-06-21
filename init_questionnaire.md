# FastAPI Server Template - Initialization Questionnaire

> **Note:** The current project version is always sourced from the `[project]` section in `pyproject.toml`. Please reference this version in your request for traceability.

Welcome to the FastAPI Server Template! This questionnaire will help us understand your requirements and customize the template for your specific needs.

## Project Information

### 1. Project Overview
- **Project Name**: Example CRM API
- **Project Description**: REST API for managing customer records, notes, and tasks for a small business CRM.
- **Primary Use Case**: Internal tool for sales and support staff to manage customer data and follow-ups.
- **Expected User Base**: 10-20 internal users

### 2. Technical Requirements

#### Database & Storage
- [x] PostgreSQL database needed
- [x] Google Cloud Storage integration needed
- [ ] Other database requirements: None
- [x] File upload/storage requirements: Store PDF contracts and images per customer

#### Authentication & Security
- [x] User authentication system needed
- [x] API key authentication (already included)
- [ ] OAuth integration needed
- [x] Role-based access control needed
- [ ] Other security requirements: Only allow access from company VPN

#### API Features
- [x] REST API endpoints needed
- [ ] WebSocket support needed
- [ ] GraphQL support needed
- [x] File upload endpoints needed
- [x] Background job processing needed
- [ ] Other API features: Bulk import/export of customer data

#### External Integrations
- [x] Third-party API integrations needed
- [x] Email service integration needed (SendGrid)
- [ ] Payment processing needed
- [ ] Notification services needed
- [ ] Other integrations: None

### 3. Deployment & Infrastructure

#### Deployment Environment
- [x] Google Cloud Platform (already configured)
- [ ] AWS
- [ ] Azure
- [ ] Self-hosted
- [ ] Other: None

#### Scaling Requirements
- [x] Expected traffic volume: 100-200 requests/day
- [ ] Auto-scaling needed
- [ ] Load balancing needed
- [ ] CDN requirements: None

### 4. Development Workflow

#### Testing Requirements
- [x] Unit testing (already included)
- [x] Integration testing needed
- [ ] End-to-end testing needed
- [ ] Performance testing needed
- [ ] Other testing requirements: None

#### CI/CD Requirements
- [x] Automated testing on pull requests (already included)
- [x] Automated deployment needed
- [ ] Staging environment needed
- [ ] Blue-green deployment needed
- [ ] Other CI/CD requirements: None

### 5. Monitoring & Observability

#### Logging & Monitoring
- [x] Application logging (already included)
- [x] Performance monitoring needed (Stackdriver)
- [x] Error tracking needed (Sentry)
- [x] Health checks (already included)
- [ ] Other monitoring needs: None

### 6. Additional Requirements

#### Documentation
- [x] API documentation (already included)
- [x] User documentation needed (internal wiki)
- [ ] Developer documentation needed
- [ ] Other documentation needs: None

#### Compliance & Standards
- [x] GDPR compliance needed
- [ ] HIPAA compliance needed
- [ ] SOC 2 compliance needed
- [ ] Other compliance requirements: None

### 7. Timeline & Priorities

- **Project Timeline**: 4 weeks
- **Priority Features** (list in order of importance):
  1. Customer CRUD API
  2. User authentication & RBAC
  3. File upload/download
  4. Email integration
  5. Bulk import/export

### 8. Additional Notes

Please provide any additional context, requirements, or constraints that should be considered:

- Must be easy to deploy and maintain by a small team
- Prefer minimal external dependencies
- Should support future integration with a mobile app

---

**Next Steps**: 
1. Fill out this questionnaire completely
2. Save it as `current_request.md` in the root directory
3. The AI agent will analyze your requirements and create a detailed implementation plan
4. The agent will follow TDD and documentation-based approach to fulfill your request

**Note**: This template is designed to be flexible and can be customized for various use cases. The more detailed your requirements, the better we can tailor the solution to your needs. 