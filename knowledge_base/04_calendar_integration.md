# Google Calendar Integration

## Overview

Jayden integrates natively with Google Calendar to enable your voice assistant to schedule, reschedule, and cancel appointments on behalf of your customers and team members. This integration is available on all plans (Starter, Pro, and Enterprise).

The calendar integration is one of our most popular features, used by healthcare providers, consulting firms, sales teams, and service businesses to automate appointment management entirely through voice or chat interactions.

## Setup Instructions

### Prerequisites
- A Google Workspace account (personal Gmail accounts are also supported)
- Admin access to the Jayden dashboard
- Google Calendar API enabled in your Google Cloud Console

### Step-by-Step Configuration

1. **Navigate to Integrations**: Log in to the Jayden dashboard and go to **Settings > Integrations > Calendar**.

2. **Select Google Calendar**: Click "Connect Google Calendar" and sign in with your Google account.

3. **Grant Permissions**: Jayden requires the following Google Calendar permissions:
   - `calendar.events.read` -- View events on your calendar
   - `calendar.events.write` -- Create and modify events
   - `calendar.settings.read` -- Read calendar settings (for timezone detection)

4. **Select Calendars**: Choose which calendars the voice assistant can access. You can connect multiple calendars (e.g., separate calendars for different team members or departments).

5. **Configure Availability Rules**: Set the rules for when appointments can be booked:
   - Business hours (e.g., Monday--Friday, 9:00 AM -- 5:00 PM)
   - Appointment duration options (15 min, 30 min, 60 min)
   - Buffer time between appointments (e.g., 10 minutes)
   - Maximum advance booking window (e.g., up to 30 days out)
   - Blocked dates and holidays

6. **Test the Integration**: Use the built-in test panel to simulate a scheduling conversation and verify events are created correctly.

## How It Works

### Booking Flow
When a customer requests an appointment, the voice assistant follows this flow:

1. **Identify Purpose**: Asks what the appointment is for (if not already stated).
2. **Check Availability**: Queries Google Calendar in real time to find open slots.
3. **Offer Options**: Presents 2-3 available time slots to the customer: "I have openings this Thursday at 10 AM, Friday at 2 PM, or next Monday at 9 AM. Which works best for you?"
4. **Confirm Details**: Reads back the selected date, time, and purpose for confirmation.
5. **Create Event**: Books the appointment on Google Calendar with all relevant details.
6. **Send Confirmation**: Triggers a confirmation email or SMS to the customer (configurable).

### Rescheduling Flow
1. The customer provides their name or confirmation number.
2. The assistant locates the existing appointment via Google Calendar search.
3. New available time slots are presented.
4. The original event is updated with the new time.
5. Updated confirmation is sent to all parties.

### Cancellation Flow
1. The customer identifies their appointment.
2. The assistant confirms the appointment details.
3. Upon confirmation, the event is removed from Google Calendar.
4. A cancellation notification is sent.

## Advanced Features

### Multi-Staff Scheduling
For businesses with multiple team members, Jayden can:
- Route appointments to specific staff based on service type or expertise
- Show combined availability across team members
- Balance appointment load evenly using round-robin assignment
- Respect individual staff schedules and time-off

### Timezone Handling
- Automatically detects the caller's timezone from their phone number area code or explicit mention
- Converts all times to the caller's local timezone during conversation
- Stores events in the correct timezone on Google Calendar
- Handles daylight saving time transitions seamlessly

### Reminder System
- Automated reminders via SMS or email at configurable intervals (e.g., 24 hours before, 1 hour before)
- Customers can reply to reminders to confirm or reschedule
- No-show tracking and automated follow-up

### Conflict Prevention
- Real-time availability checking prevents double-bookings
- Events created by other means (manual, other apps) are immediately reflected
- Hold-and-release mechanism: a tentative hold is placed on a slot during the conversation, released if the customer doesn't confirm within 5 minutes

## Supported Calendar Fields

When creating an event, Jayden populates:
- **Title**: e.g., "Consultation -- John Smith"
- **Date and Time**: Start and end time in the correct timezone
- **Description**: Summary of the appointment purpose and any notes from the conversation
- **Location**: Physical address or video meeting link (auto-generates Google Meet link if configured)
- **Attendees**: Customer email address (if collected)
- **Reminders**: Based on your configured reminder settings
- **Custom Metadata**: Jayden interaction ID for cross-referencing

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Calendar not syncing | Verify OAuth token is valid under Settings > Integrations. Re-authenticate if expired. |
| Wrong timezone on events | Check timezone settings in both Jayden and Google Calendar. Ensure Google Calendar timezone matches your business location. |
| Double bookings occurring | Enable "Conflict Prevention" in calendar settings. Ensure buffer time is configured. |
| Events missing attendees | Verify that email collection is enabled in your conversation flow. |
| "Insufficient permissions" error | Re-authorize the Google Calendar connection and ensure all required scopes are granted. |

## API Access

Developers can interact with the calendar integration programmatically via the Jayden API. See the [API Reference](./08_api_reference.md) for endpoints related to:
- `POST /api/v1/appointments` -- Create an appointment
- `GET /api/v1/appointments/{id}` -- Retrieve appointment details
- `PATCH /api/v1/appointments/{id}` -- Reschedule an appointment
- `DELETE /api/v1/appointments/{id}` -- Cancel an appointment
- `GET /api/v1/availability` -- Query available time slots
