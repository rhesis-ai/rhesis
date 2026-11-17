// Session duration in days
export const SESSION_DURATION_DAYS = 7;

// Session duration in seconds
export const SESSION_DURATION_SECONDS = SESSION_DURATION_DAYS * 24 * 60 * 60;

// Session duration in milliseconds
export const SESSION_DURATION_MS = SESSION_DURATION_SECONDS * 1000;

// 403 detail the backend sends when an account is locked until it verifies its email
export const EMAIL_NOT_VERIFIED = 'email_not_verified';

// 403 detail when mail to the address hard-bounced, so it can't be verified
export const EMAIL_UNDELIVERABLE = 'email_undeliverable';
