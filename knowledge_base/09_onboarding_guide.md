# Jayden Onboarding Guide -- Getting Started

## Welcome to Jayden

Congratulations on choosing Jayden for your customer support automation. This guide walks you through the complete setup process, from creating your account to deploying your first AI-powered voice assistant. Most businesses complete the initial setup in under one hour.

## Step 1: Create Your Account

1. Visit [Jayden.com/signup](https://Jayden.com/signup) and enter your business email.
2. Verify your email address by clicking the confirmation link.
3. Complete your company profile:
   - Company name and industry
   - Estimated monthly interaction volume
   - Primary use case (customer support, sales, scheduling, etc.)
4. Choose your plan (Starter, Pro, or Enterprise) or start with the 14-day free trial.

**Tip**: If you are evaluating Jayden for an enterprise deployment, contact sales@Jayden.com to request a guided demo and custom trial environment.

## Step 2: Configure Your Voice Assistant Persona

Your voice assistant's persona defines how it speaks, what tone it uses, and how it represents your brand.

### Setting Up the Persona

Navigate to **Dashboard > Assistant > Persona** and configure:

- **Name**: Give your assistant a name (e.g., "Alex", "Maya", "Sam"). This is the name it will use when introducing itself to callers.
- **Voice**: Select from 50+ voice profiles or request a custom voice clone (Pro and Enterprise). Preview each voice in the dashboard before selecting.
- **Language**: Choose the primary language and any secondary languages. The assistant will automatically detect and switch languages mid-conversation if needed.
- **Tone**: Choose from professional, friendly, casual, or formal. You can also write custom tone instructions (e.g., "Be warm and empathetic, use the customer's first name, avoid technical jargon").
- **Greeting**: Customize the welcome message. Example: "Hello! Thanks for calling Acme Corp. I'm Alex, your virtual assistant. How can I help you today?"

### Defining Behavior Rules

Under **Assistant > Behavior**, set guardrails for your assistant:

- **Escalation Triggers**: Define when the assistant should transfer to a human (e.g., complaints, billing disputes over a certain amount, or when the caller explicitly asks for a person).
- **Restricted Topics**: List topics the assistant should not discuss (e.g., legal advice, competitor comparisons, unannounced products).
- **Confirmation Requirements**: Require the assistant to confirm before taking certain actions (e.g., canceling a subscription, processing a refund).
- **Fallback Behavior**: What the assistant should do when it does not know the answer -- escalate, offer to take a message, or suggest alternative resources.

## Step 3: Build Your Knowledge Base

The knowledge base is the foundation of your assistant's intelligence. It contains the information your assistant uses to answer customer questions.

### Uploading Content

Go to **Dashboard > Knowledge Base > Upload** and add your content:

1. **Upload Files**: Drag and drop files in supported formats (Markdown, PDF, Word, HTML, CSV, or plain text).
2. **Connect Sources**: Link to external sources such as your Zendesk help center, Notion workspace, or Confluence space for automatic syncing.
3. **Manual Entry**: Create knowledge articles directly in the Jayden editor.

### Best Practices for Knowledge Base Content

- **Be specific**: Include exact product names, prices, URLs, and procedures. The assistant retrieves and presents this information directly.
- **Use Q&A format**: Structuring content as questions and answers improves retrieval accuracy. Example: "Q: What is the return policy? A: We offer a 30-day no-questions-asked return policy for all products."
- **Keep content current**: Set a review schedule to update outdated information. Stale knowledge is worse than no knowledge -- it leads to incorrect answers.
- **Cover edge cases**: Document common follow-up questions and unusual scenarios. Think about what your human agents frequently look up.
- **Organize by topic**: Use clear file names and headers. The AI uses document structure to improve retrieval relevance.

## Step 4: Connect Your Channels

### Phone (Voice)

Navigate to **Settings > Channels > Phone** and choose your connection method:

- **Twilio**: Enter your Twilio Account SID and Auth Token. Select which Twilio phone numbers should route to Jayden.
- **SIP Trunk**: Configure your PBX to forward calls to the SIP endpoint provided in the dashboard.
- **Jayden Number**: Purchase a new local or toll-free number directly from Jayden.

Test the connection by making a call to your configured number.

### Web Chat

Navigate to **Settings > Channels > Web Chat** to generate your chat widget code:

```html
<script src="https://cdn.Jayden.com/widget.js"></script>
<script>
  Jayden.init({
    accountId: 'your_account_id',
    persona: 'default',
    position: 'bottom-right',
    primaryColor: '#4F46E5'
  });
</script>
```

Paste this snippet before the closing `</body>` tag on your website. The widget is fully customizable -- adjust colors, position, welcome message, and behavior.

### Other Channels

- **WhatsApp**: Requires a WhatsApp Business API account. Connect via **Settings > Channels > WhatsApp**.
- **SMS**: Configure via Twilio integration or Jayden phone numbers.
- **Slack/Teams**: Install the Jayden app from the respective marketplace.

## Step 5: Test and Launch

### Testing Checklist

Before going live, verify:

- [ ] Voice assistant greets callers correctly
- [ ] Knowledge base answers are accurate for your top 20 most common questions
- [ ] Escalation to human agents works properly
- [ ] Calendar scheduling creates events correctly (if applicable)
- [ ] All connected channels are functioning
- [ ] Analytics dashboard shows test interactions
- [ ] Webhook notifications are received by your systems (if configured)

### Soft Launch

We recommend a phased rollout:
1. **Week 1**: Route 10-20% of traffic to Jayden while monitoring quality.
2. **Week 2**: Increase to 50% if quality metrics are satisfactory.
3. **Week 3**: Move to full deployment.

This approach lets you catch and fix issues before they affect all customers.

## Step 6: Monitor and Optimize

After launch, use the analytics dashboard to track performance:
- **Resolution Rate**: Percentage of interactions resolved without human escalation. Target: >70%.
- **CSAT Score**: Customer satisfaction from post-interaction surveys. Target: >4.5/5.0.
- **Escalation Reasons**: Understand why the AI escalates to identify knowledge gaps.
- **Top Topics**: See what customers ask about most and ensure those topics are well-covered.

Review the **Conversations** tab weekly to spot incorrect answers and add corrections to your knowledge base. Continuous improvement is key to maximizing the value of your AI assistant.

## Need Help?

- **Pro Plan**: Schedule your complimentary 60-minute onboarding session at [Jayden.com/onboarding](https://Jayden.com/onboarding).
- **Enterprise Plan**: Your dedicated Account Manager will guide you through the entire setup process.
- **All Plans**: Reach out to support@Jayden.com or visit our Community Forum at [community.Jayden.com](https://community.Jayden.com).
