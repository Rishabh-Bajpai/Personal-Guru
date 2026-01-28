# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in Personal Guru, please report it responsibly.

### How to Report

1. **DO NOT** create a public GitHub issue for security vulnerabilities
2. Email details to the maintainer [samosa.ai.com@gmail.com] or use [GitHub's private vulnerability reporting](https://github.com/Rishabh-Bajpai/Personal-Guru/security/advisories/new)

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Resolution**: Depends on severity, typically within 30 days

### What to Expect

- We will acknowledge your report promptly
- We will keep you informed of our progress
- We will credit you in the fix announcement (unless you prefer anonymity)

## Security Considerations

### Local-First Design

Personal Guru is designed to run locally with privacy in mind:

- **Data Storage**: All user data is stored locally in your PostgreSQL database
- **AI Processing**: Connects to your chosen LLM provider (local or cloud)
- **No Telemetry by Default in alpha version**: Optional, opt-in telemetry only in alpha version. In beta version, telemetry will be enabled by default and will be used to improve the app.

### Best Practices for Users

1. **Keep Dependencies Updated**

   ```bash
   pip install --upgrade .
   ```

2. **Use Strong Database Credentials**
   - Change default PostgreSQL password in production

3. **Secure Your LLM API Keys**
   - Never commit `.env` files with real keys
   - Use environment variables in production

4. **HTTPS for Production**
   - Use a reverse proxy with SSL certificates
   - See README for HTTPS setup instructions

5. **Code Sandbox**
   - The code execution sandbox is experimental
   - Review the security implications before enabling

## Scope

This security policy covers the Personal Guru application. Third-party dependencies have their own security policies.

---

Thank you for helping keep Personal Guru secure! 🔒
