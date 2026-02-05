# Jayden Security and Compliance

## Our Commitment to Security

Security is foundational to everything we build at Jayden. As a platform that processes sensitive customer interactions -- including voice conversations, personal data, and business information -- we maintain the highest standards of data protection, infrastructure security, and regulatory compliance.

This document provides an overview of our security practices, certifications, and compliance posture. For detailed security documentation or to request our SOC 2 report, contact security@Jayden.com.

## Certifications and Compliance

### SOC 2 Type II
Jayden has achieved **SOC 2 Type II** certification, audited annually by an independent third-party firm. Our SOC 2 report covers the Trust Services Criteria for Security, Availability, Processing Integrity, Confidentiality, and Privacy. Customers can request a copy of our latest SOC 2 report under NDA.

### GDPR (General Data Protection Regulation)
Jayden is fully compliant with the European Union's GDPR. Our compliance measures include:
- **Data Processing Agreement (DPA)**: Available for all customers upon request.
- **Lawful Basis**: We process personal data only under legitimate legal bases (contract performance, legitimate interest, or consent).
- **Data Subject Rights**: We support all data subject rights including access, rectification, erasure, portability, and restriction of processing.
- **Data Protection Officer**: Our DPO can be reached at dpo@Jayden.com.
- **EU Data Residency**: EU customers can elect to have all data stored exclusively in our eu-west-1 (Ireland) region.

### HIPAA (Health Insurance Portability and Accountability Act)
Jayden offers **HIPAA-compliant configurations** for healthcare customers on the Enterprise plan. This includes:
- Business Associate Agreement (BAA) execution
- Encrypted storage of protected health information (PHI)
- Access controls and audit logging for PHI
- Separate, hardened infrastructure for healthcare workloads

### CCPA (California Consumer Privacy Act)
Jayden complies with the CCPA and the California Privacy Rights Act (CPRA). California residents can exercise their privacy rights by contacting privacy@Jayden.com or through the in-app privacy settings.

### PCI DSS
Jayden does **not** process or store credit card numbers directly. For customers who need to collect payment information via voice, we offer a secure IVR passthrough mode that routes the caller to a PCI-compliant payment processor. The AI assistant is paused during payment collection to ensure card data never enters our systems.

## Data Encryption

### In Transit
- All data in transit is encrypted using **TLS 1.3** (minimum TLS 1.2).
- API communications, webhook deliveries, and dashboard access all use HTTPS.
- Voice traffic is encrypted using **SRTP** (Secure Real-time Transport Protocol) for telephony and **DTLS-SRTP** for WebRTC.

### At Rest
- All stored data is encrypted using **AES-256** encryption.
- Encryption keys are managed through AWS Key Management Service (KMS) with automatic key rotation.
- Database backups are encrypted with separate keys.
- Enterprise customers can provide their own encryption keys (BYOK -- Bring Your Own Key) for maximum control.

## Infrastructure Security

### Cloud Infrastructure
Jayden runs on **Amazon Web Services (AWS)** with the following security measures:
- Deployed across multiple Availability Zones for high availability
- Virtual Private Cloud (VPC) isolation with strict security group rules
- No public-facing servers other than load balancers and API gateways
- Infrastructure managed as code (Terraform) with version-controlled, peer-reviewed changes
- Automated vulnerability scanning of all container images and dependencies

### Network Security
- Web Application Firewall (WAF) protects all public endpoints
- DDoS protection through AWS Shield Advanced
- Intrusion detection and prevention systems (IDS/IPS) monitor all network traffic
- Regular penetration testing by independent security firms (at least annually)

### Access Control
- Principle of least privilege enforced across all systems
- Multi-factor authentication (MFA) required for all employees accessing production systems
- Just-in-time access provisioning for production environments
- Quarterly access reviews to revoke unnecessary permissions
- All production access is logged and monitored

## Application Security

### Secure Development Lifecycle
- Security reviews are part of every code change through pull request reviews
- Static Application Security Testing (SAST) runs on every build
- Dynamic Application Security Testing (DAST) runs weekly against staging environments
- Dependency vulnerability scanning with automated alerts and remediation
- Security-focused training for all engineering staff annually

### Authentication and Authorization
- **Customer Dashboard**: Supports email/password with MFA (TOTP and WebAuthn/FIDO2) and SSO via SAML 2.0 and OpenID Connect (Enterprise).
- **API**: Bearer token authentication with scoped permissions. Tokens can be restricted by IP address.
- **Role-Based Access Control (RBAC)**: Define custom roles (Admin, Manager, Agent, Viewer) with granular permissions for dashboard access.

## Data Privacy and Retention

### Data Minimization
Jayden collects and processes only the data necessary to provide the service. We do not sell customer data or use it for advertising purposes. Conversation data is used solely for service delivery, quality assurance, and analytics within the customer's own account.

### Data Retention Policies
Default retention periods by plan:
- **Starter**: Conversation transcripts and recordings retained for 30 days
- **Pro**: Retained for 12 months
- **Enterprise**: Custom retention policies (including indefinite retention or reduced retention for compliance)

Customers can configure shorter retention periods at any time. When data is deleted (either by policy or manual request), it is permanently removed from all systems, including backups, within 30 days.

### Data Portability
Customers can export their data at any time in standard formats:
- Conversation transcripts: JSON or CSV
- Audio recordings: WAV or MP3
- Analytics data: CSV or JSON
- Knowledge base content: Original format or Markdown

Bulk export is available via the API or by contacting support.

## Incident Response

Jayden maintains a formal incident response plan that is tested regularly through tabletop exercises and simulated incidents.

### Incident Response Process
1. **Detection**: Automated monitoring detects anomalies and potential security events 24/7.
2. **Triage**: On-call security engineer assesses severity within 15 minutes.
3. **Containment**: Immediate actions to limit the scope and impact of the incident.
4. **Investigation**: Root cause analysis with forensic evidence preservation.
5. **Remediation**: Fix the underlying vulnerability and verify resolution.
6. **Notification**: Affected customers are notified within 72 hours (or sooner per contractual requirements).
7. **Post-Mortem**: Publish an internal post-mortem with lessons learned and preventive measures.

### Security Contact
To report a security vulnerability, email security@Jayden.com. We participate in a responsible disclosure program and acknowledge reports within 24 hours. We do not pursue legal action against good-faith security researchers.

## Vendor and Subprocessor Management

Jayden maintains a list of subprocessors involved in data processing. Key subprocessors include:
- **Amazon Web Services (AWS)**: Cloud infrastructure hosting
- **Twilio**: Telephony services
- **Google Cloud**: Calendar integration services
- **Stripe**: Payment processing

A full list of subprocessors is available at [Jayden.com/subprocessors](https://Jayden.com/subprocessors). Customers are notified 30 days in advance of any new subprocessor additions.
