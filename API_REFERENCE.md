# Channel Manager API Reference

> **Version:** 2.0
> **Purpose:** API integration reference for Casita PMS
> **Last Updated:** January 2026

---

## Table of Contents

1. [API Types](#api-types)
2. [Authentication](#authentication)
3. [Base Configuration](#base-configuration)
4. [Booking Engine API](#booking-engine-api)
5. [Open API - Listings](#open-api---listings)
6. [Calendar & Pricing API](#calendar--pricing-api)
7. [Reservations API](#reservations-api)
8. [Messaging & Conversations API](#messaging--conversations-api)
9. [Saved Replies API](#saved-replies-api)
10. [Guests API](#guests-api)
11. [Rate Limits & Best Practices](#rate-limits--best-practices)
12. [Error Handling](#error-handling)
13. [Casita-Specific Implementation Notes](#casita-specific-implementation-notes)

---

## API Types

Guesty provides two separate APIs with different purposes and credentials:

| API | Purpose | Base URL | Scope |
|-----|---------|----------|-------|
| **Booking Engine API** | Direct bookings, website integration | `https://booking.guesty.com/api/v1` | `booking_engine:api` |
| **Open API** | Full PMS access, management | `https://open-api.guesty.com/v1` | `open-api` |

> **Note:** Each API requires separate credentials. Booking Engine API credentials cannot access Open API endpoints and vice versa.

---

## Authentication

### OAuth2 Client Credentials Flow

Guesty uses OAuth 2.0 with **client credentials grant** (server-to-server, no user interaction).

### Booking Engine API Authentication

**Token Endpoint:**
```
POST https://booking.guesty.com/oauth2/token
```

**Request Body (form-encoded):**
```
grant_type=client_credentials
scope=booking_engine:api
client_id=YOUR_BOOKING_CLIENT_ID
client_secret=YOUR_BOOKING_CLIENT_SECRET
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 86400,
  "scope": "booking_engine:api"
}
```

### Open API Authentication

**Token Endpoint:**
```
POST https://open-api.guesty.com/oauth2/token
```

**Request Body (form-encoded):**
```
grant_type=client_credentials
scope=open-api
client_id=YOUR_OPEN_API_CLIENT_ID
client_secret=YOUR_OPEN_API_CLIENT_SECRET
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 86400,
  "scope": "open-api"
}
```

### Token Management
- **Expiration:** 24 hours (86400 seconds)
- **Refresh Strategy:** Refresh 30-60 minutes before expiration or on 401/403 error
- **Limit:** Max 5 tokens per 24 hours per client_id
- **Best Practice:** Cache token and reuse for 24 hours to avoid rate limits on auth endpoint
- **Usage:** `Authorization: Bearer {access_token}` in all requests

---

## Base Configuration

| API | Base URL |
|-----|----------|
| Booking Engine API | `https://booking.guesty.com/api/v1` |
| Open API | `https://open-api.guesty.com/v1` |

**Common Headers:**
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

---

## Booking Engine API

The Booking Engine API is designed for building custom booking websites and widgets.

### Search Available Listings
```
GET /search
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `checkIn` | string | Check-in date (YYYY-MM-DD) |
| `checkOut` | string | Check-out date (YYYY-MM-DD) |
| `guests` | int | Total number of guests |
| `adults` | int | Number of adults |
| `children` | int | Number of children |
| `location` | string | Location filter |

**Example Request:**
```
GET https://booking.guesty.com/api/v1/search?checkIn=2026-02-01&checkOut=2026-02-05&adults=2
```

### Get All Listings
```
GET /listings
```

### Get Listing by ID
```
GET /listings/{listingId}
```

### Get Listing Availability Calendar
```
GET /listings/{listingId}/calendar
```

### Get Cities
```
GET /cities
```

### Reservation Quote Flow

#### Create Quote
```
POST /quotes
```

**Request Body:**
```json
{
  "listingId": "listing_id",
  "checkIn": "2026-02-01",
  "checkOut": "2026-02-05",
  "guests": 2
}
```

#### Get Quote
```
GET /quotes/{quoteId}
```

#### Create Reservation from Quote
```
POST /quotes/{quoteId}/reservations
```

### Rate Limits (Booking Engine API)
- 5 requests per second
- 275 requests per minute
- 16,500 requests per hour

---

## Open API - Listings

> **Note:** These endpoints require Open API credentials (not Booking Engine API).

### Get All Listings
```
GET /listings
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Max results per page (default: 25, max: 100) |
| `skip` | int | Number of results to skip for pagination |
| `fields` | string | Comma-separated list of fields to return |
| `filters` | JSON | MongoDB-style filters (URL-encoded) |
| `sort` | string | Field to sort by |

**Common Filters:**
```json
// Active listings only
{"active": {"$eq": true}}

// MTL (Multi-Unit) properties
{"type": {"$eq": "MTL"}}

// Single properties
{"type": {"$eq": "SINGLE"}}

// Child units of a parent
{"type": {"$eq": "MTL_CHILD"}, "mtl.p": {"$in": ["PARENT_ID"]}}
```

**Response Structure:**
```json
{
  "results": [
    {
      "_id": "listing_id",
      "title": "Property Name",
      "nickname": "Short name",
      "type": "MTL" | "SINGLE" | "MTL_CHILD",
      "active": true,
      "address": {
        "full": "123 Beach Dr, Miami Beach, FL 33139",
        "street": "123 Beach Dr",
        "city": "Miami Beach",
        "state": "FL",
        "zipcode": "33139",
        "country": "US",
        "lat": 25.7826,
        "lng": -80.1340
      },
      "prices": {
        "basePrice": 200,
        "minPrice": 100,
        "maxPrice": 500,
        "currency": "USD"
      },
      "bedrooms": 2,
      "bathrooms": 1,
      "accommodates": 4,
      "propertyType": "Apartment"
    }
  ],
  "count": 50,
  "limit": 25,
  "skip": 0
}
```

### Get Single Listing
```
GET /listings/{listingId}
```

### Listing Types

| Type | Description |
|------|-------------|
| `SINGLE` | Standalone property |
| `MTL` | Multi-unit property (parent) |
| `MTL_CHILD` | Unit within a multi-unit property |

---

## Calendar & Pricing API

### Get Calendar
```
GET /availability-pricing-api/calendar/listings/{listingId}
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `startDate` | string | Start date (YYYY-MM-DD) |
| `endDate` | string | End date (YYYY-MM-DD) |

**Response:**
```json
{
  "data": {
    "2026-01-20": {
      "date": "2026-01-20",
      "price": 250,
      "basePrice": 200,
      "minNights": 2,
      "available": true,
      "status": "available"
    }
  }
}
```

### Update Calendar/Pricing
```
PUT /availability-pricing-api/calendar/listings/{listingId}
```

**Request Body:**
```json
{
  "startDate": "2026-01-20",
  "endDate": "2026-01-25",
  "price": 300,
  "minNights": 3,
  "available": true
}
```

### Airbnb Smart Pricing Integration

When Airbnb Smart Pricing is enabled on a listing:
- The `price` field in calendar data reflects the smart pricing recommendation
- `basePrice` shows the manually set base price
- Updates via PUT override smart pricing for specified dates

---

## Reservations API

### Get Reservations
```
GET /reservations
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Max results |
| `skip` | int | Pagination offset |
| `fields` | string | Fields to return |
| `filters` | JSON | MongoDB-style filters |

**Common Filters:**
```json
// By listing
{"listingId": {"$eq": "listing_id"}}

// By date range
{"checkIn": {"$gte": "2026-01-01"}, "checkOut": {"$lte": "2026-12-31"}}

// By status
{"status": {"$in": ["confirmed", "inquiry"]}}
```

**Response:**
```json
{
  "results": [
    {
      "_id": "reservation_id",
      "confirmationCode": "ABC123",
      "listingId": "listing_id",
      "checkIn": "2026-01-20",
      "checkOut": "2026-01-25",
      "status": "confirmed",
      "source": "Airbnb",
      "guest": {
        "_id": "guest_id",
        "firstName": "John",
        "lastName": "Doe",
        "email": "john@example.com",
        "phone": "+1234567890"
      },
      "money": {
        "hostPayout": 500,
        "totalPrice": 600,
        "currency": "USD"
      }
    }
  ]
}
```

---

## Messaging & Conversations API

### Get All Conversations
```
GET /communication/conversations
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Max results (default: 50) |
| `listingId` | string | Filter by listing |

**Response:**
```json
{
  "results": [
    {
      "_id": "conversation_id",
      "listingId": "listing_id",
      "guest": {
        "_id": "guest_id",
        "firstName": "John",
        "lastName": "Doe",
        "fullName": "John Doe"
      },
      "listing": {
        "_id": "listing_id",
        "title": "Beach Villa"
      },
      "lastMessage": {
        "body": "What time is check-in?",
        "sentAt": "2026-01-20T10:30:00Z"
      },
      "checkIn": "2026-01-25",
      "checkOut": "2026-01-30"
    }
  ]
}
```

### Get Conversation by ID
```
GET /communication/conversations/{conversationId}
```

### Get Conversation Messages (Posts)
```
GET /communication/conversations/{conversationId}/posts
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Max messages to return |

**Response:**
```json
{
  "results": [
    {
      "_id": "post_id",
      "body": "What time is check-in?",
      "from": "guest",
      "sentAt": "2026-01-20T10:30:00Z",
      "type": "fromGuest"
    }
  ]
}
```

### Send Message
```
POST /communication/conversations/{conversationId}/send-message
```

**Request Body:**
```json
{
  "body": "Check-in is at 3 PM. Let us know if you need early check-in!",
  "module": "airbnb2"
}
```

**Module Types:**
- `airbnb2` - Airbnb messaging
- `email` - Email
- `sms` - SMS (if configured)

### Create Draft (Without Sending)
```
POST /communication/conversations/{conversationId}/posts
```

**Request Body:**
```json
{
  "body": "Draft message for review..."
}
```

---

## Saved Replies API

### Get All Saved Replies
```
GET /saved-replies
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Max results |

**Response:**
```json
{
  "results": [
    {
      "_id": "reply_id",
      "title": "Check-in Instructions",
      "body": "Check-in is at 3 PM. Your door code will be sent 24 hours before arrival.",
      "category": "Check-in",
      "keywords": ["check-in", "arrival", "access"]
    }
  ]
}
```

### Get Saved Reply by ID
```
GET /saved-replies/{replyId}
```

### Get Saved Replies by Listing
```
GET /saved-replies/listing/{listingId}
```

### Create Saved Reply
```
POST /saved-replies
```

**Request Body:**
```json
{
  "title": "Parking Information",
  "body": "Free parking is available in the garage. Use code 1234 at the gate.",
  "category": "Amenities"
}
```

### Update Saved Reply
```
PUT /saved-replies/{replyId}
```

### Delete Saved Reply
```
DELETE /saved-replies/{replyId}
```

---

## Guests API

### Get All Guests
```
GET /guests
```

### Get Guest by ID
```
GET /guests/{guestId}
```

### Update Guest
```
PUT /guests/{guestId}
```

---

## Rate Limits & Best Practices

### Rate Limits
- **Per-minute limits:** Varies by endpoint (typically 60-120 requests/minute)
- **Token limits:** Max 5 tokens per 24 hours per client_id
- **Batch operations:** Use pagination, don't request all data at once

### Best Practices

1. **Token Caching:**
   - Cache access token for ~23 hours
   - Refresh proactively before expiration

2. **Pagination:**
   - Use `limit` and `skip` for large datasets
   - Default batch size: 25-50 items

3. **Field Selection:**
   - Use `fields` parameter to request only needed data
   - Reduces payload size and improves performance

4. **Error Handling:**
   - Implement exponential backoff for rate limits
   - Retry on 429 (Too Many Requests) with delay

---

## Error Handling

### Common HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 400 | Bad Request | Check request format |
| 401 | Unauthorized | Refresh token |
| 403 | Forbidden | Check permissions/refresh token |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Wait and retry with backoff |
| 500 | Server Error | Retry after delay |

### Error Response Format
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Description of what went wrong"
  }
}
```

---

## Casita-Specific Implementation Notes

### Property Hierarchy

In Casita PMS, we map Guesty listings as follows:

| Guesty Type | Casita Entity | Notes |
|-------------|---------------|-------|
| `MTL` | Property | Parent property with units |
| `MTL_CHILD` | Unit | Individual rentable unit |
| `SINGLE` | Property + 1 Unit | Standalone property |

### CasitAI Bot Integration

**Priority Order for Guest Responses:**
1. Match saved replies from Guesty
2. Use hospitality knowledge (check-in times, etc.)
3. Reference past conversation examples
4. Generate AI response with Ollama
5. Escalate to human agent if low confidence or negative sentiment

**Escalation Keywords:**
- refund, cancel, complaint, emergency, urgent
- manager, legal, lawyer, police
- damage, injury, safety
- discrimination, harassment

### Calendar/Smart Pricing Sync

When syncing prices:
1. Pull calendar data via GET endpoint
2. `price` field reflects current (potentially smart) pricing
3. `basePrice` is the manually set base
4. Push updates via PUT to override specific dates

### Conversation Training

To train CasitAI on your team's style:
1. Fetch all conversations via `/communication/conversations`
2. Get messages for each via `/communication/conversations/{id}/posts`
3. Extract guest question -> host response pairs
4. Use as few-shot examples for AI responses

---

## Environment Variables

```env
# Guesty API Credentials
GUESTY_CLIENT_ID=your_client_id
GUESTY_CLIENT_SECRET=your_client_secret

# API Type Selection
# Set to 'true' for Booking Engine API, 'false' for Open API
GUESTY_USE_BOOKING_API=true

# Ollama AI Bot Configuration
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

### API Credential Types

| Environment Variable | Booking Engine API | Open API |
|---------------------|-------------------|----------|
| `GUESTY_CLIENT_ID` | From BEAPI settings | From Open API settings |
| `GUESTY_CLIENT_SECRET` | From BEAPI settings | From Open API settings |
| `GUESTY_USE_BOOKING_API` | `true` | `false` |

> **Important:** Booking Engine API and Open API credentials are NOT interchangeable. Get the correct credentials from the respective sections in Guesty settings.

---

## Quick Reference

### Booking Engine API Endpoints

| Purpose | Method | Endpoint |
|---------|--------|----------|
| Search listings | GET | `/search` |
| Get all listings | GET | `/listings` |
| Get listing | GET | `/listings/{id}` |
| Get calendar | GET | `/listings/{id}/calendar` |
| Get cities | GET | `/cities` |
| Create quote | POST | `/quotes` |
| Get quote | GET | `/quotes/{id}` |
| Create reservation | POST | `/quotes/{id}/reservations` |

### Open API Endpoints

| Purpose | Method | Endpoint |
|---------|--------|----------|
| Get listings | GET | `/listings` |
| Get calendar | GET | `/availability-pricing-api/calendar/listings/{id}` |
| Update pricing | PUT | `/availability-pricing-api/calendar/listings/{id}` |
| Get reservations | GET | `/reservations` |
| Get conversations | GET | `/communication/conversations` |
| Get messages | GET | `/communication/conversations/{id}/posts` |
| Send message | POST | `/communication/conversations/{id}/send-message` |
| Get saved replies | GET | `/saved-replies` |

---

*This document serves as the primary reference for Guesty API integration in Casita PMS. Last updated January 2026.*
