# Frequently Asked Questions -- Technical

## Infrastructure and Architecture

### What technology stack does Jayden use?
Jayden is built on a modern, cloud-native architecture:
- **AI/ML**: Proprietary large language models fine-tuned for customer service, running on GPU-accelerated infrastructure. We use a combination of transformer-based models for language understanding and neural vocoders for speech synthesis.
- **Speech Recognition**: Custom automatic speech recognition (ASR) engine with real-time streaming, optimized for telephony audio quality (8kHz narrowband and 16kHz wideband).
- **Backend**: Microservices architecture deployed on Kubernetes, written primarily in Python and Go.
- **Real-Time Communication**: WebRTC for browser-based voice, SIP/RTP for telephony integration.
- **Data Storage**: PostgreSQL for relational data, Redis for caching and session management, Elasticsearch for conversation search and analytics, S3-compatible object storage for audio recordings.
- **Message Queue**: Apache Kafka for event streaming between services.

### What is the system latency?
End-to-end latency from the moment a caller finishes speaking to when the AI begins responding averages **280ms** in production environments. This breaks down as:
- Speech recognition finalization: ~80ms
- Language model inference: ~120ms
- Text-to-speech generation (streaming): ~80ms

This latency is well below the 500ms threshold that humans perceive as a natural conversational pause.

### What is Jayden's uptime guarantee?
- **Starter Plan**: 99.5% uptime SLA
- **Pro Plan**: 99.9% uptime SLA (less than 8.76 hours downtime per year)
- **Enterprise Plan**: 99.99% uptime SLA (less than 52.6 minutes downtime per year)

We maintain a public status page at [status.Jayden.com](https://status.Jayden.com) with real-time system health and historical uptime data.

---

## Integration and API

### How do I connect Jayden to my phone system?
Jayden supports three methods for telephony integration:
1. **SIP Trunk**: Connect your existing PBX (e.g., Asterisk, FreeSWITCH, Cisco) via SIP trunk. We provide SIP credentials and endpoint configuration.
2. **Twilio**: If you use Twilio for your phone numbers, connect via our native Twilio integration in under 10 minutes. Simply enter your Twilio Account SID and Auth Token.
3. **Jayden Phone Numbers**: Purchase phone numbers directly through Jayden. We offer local and toll-free numbers in 40+ countries.

### Does Jayden support webhooks?
Yes. Jayden fires webhooks for a wide range of events, including:
- `conversation.started` -- A new interaction has begun
- `conversation.ended` -- An interaction has completed
- `conversation.escalated` -- The AI has transferred to a human agent
- `appointment.created` -- A new appointment was booked
- `appointment.cancelled` -- An appointment was cancelled
- `sentiment.negative` -- Negative sentiment detected above threshold

Webhooks are delivered as HTTP POST requests with JSON payloads. You can configure webhook endpoints and select which events to subscribe to in **Settings > Webhooks**.

### What is the API rate limit?
- **Pro Plan**: 10,000 API calls per month, with a burst rate of 100 requests per minute.
- **Enterprise Plan**: Custom rate limits based on your contract. Default is 100,000 calls/month with 500 requests per minute burst.
- Rate-limited requests receive a `429 Too Many Requests` response with a `Retry-After` header.

### Can I train the AI on my own data?
Yes, in two ways:
1. **Knowledge Base (RAG)**: Upload your documentation, FAQs, product manuals, and other content. The AI retrieves relevant information at query time using retrieval-augmented generation. This requires no ML expertise and updates take effect in minutes.
2. **Custom Fine-Tuning** (Enterprise only): For specialized use cases, we offer custom model fine-tuning on your conversation data. This produces a model specifically adapted to your domain, terminology, and interaction patterns. Fine-tuning typically takes 1-2 weeks and requires a minimum of 10,000 conversation examples.

---

## Voice and Speech

### Can I use my own custom voice?
Yes, on Pro and Enterprise plans. Our voice cloning process works as follows:
1. Provide 30-60 minutes of clean audio from the target speaker.
2. Our team processes the audio and trains a custom voice model (takes 3-5 business days).
3. The custom voice is available in your dashboard and via API.
4. The cloned voice can synthesize speech in any of our 28 supported languages.

All voice cloning requires written consent from the voice owner. Jayden maintains a voice consent registry for compliance.

### How does the assistant handle accents and dialects?
Our ASR engine is trained on diverse speech data covering major regional accents and dialects. For English alone, we support American, British, Australian, Indian, South African, and Irish English accents with high accuracy. The system continuously adapts during a conversation -- if it detects a non-native speaker, it automatically adjusts its recognition parameters to improve accuracy.

### What audio formats are supported?
- **Input**: PCM 16-bit (8kHz or 16kHz), G.711 (mu-law and A-law), Opus, MP3
- **Output**: PCM 16-bit (24kHz default), Opus, MP3, G.711
- For telephony channels, audio is automatically transcoded to match your phone system requirements.

---

## Troubleshooting

### The assistant is giving incorrect answers. How do I fix this?
1. **Check your knowledge base**: Ensure the correct information exists in your uploaded documents. Use the Knowledge Base search tool in the dashboard to verify what content the AI retrieves for a given query.
2. **Review conversation logs**: In the dashboard under **Analytics > Conversations**, review the specific interaction to see what knowledge was retrieved and how the AI formulated its response.
3. **Add corrections**: Create a "corrections" document in your knowledge base that explicitly addresses the incorrect response with the correct information.
4. **Adjust confidence threshold**: Under **Settings > AI Behavior**, increase the confidence threshold. This causes the AI to escalate to a human agent when it is not sufficiently confident in its answer, rather than guessing.

### Calls are dropping or audio quality is poor. What should I check?
- **Network**: Ensure stable internet connectivity with at least 100kbps bandwidth per concurrent call. Jitter should be below 30ms and packet loss below 1%.
- **Firewall**: Jayden requires UDP ports 10000-20000 to be open for RTP media traffic. SIP signaling uses TCP/UDP port 5060 (or 5061 for TLS).
- **Codec Mismatch**: Verify that your PBX supports at least one of our supported codecs (G.711, Opus).
- **SIP Configuration**: Check that your SIP trunk registration is active in the Jayden dashboard under **Settings > Telephony**.

If issues persist, contact support with your Jayden account ID and the timestamp of affected calls. Our team can access detailed call diagnostics for troubleshooting.
