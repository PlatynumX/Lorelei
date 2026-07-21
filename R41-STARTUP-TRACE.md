# R41d main-scoped startup trace

R41c failed because InitializeMessages() appears three times in rt_main.c.

R41d locates main() using whitespace-tolerant C signature matching, isolates
that function body, and inserts T08-T30 only inside main().

Report the final T-number and description visible before blackness.

No registered startup behavior is bypassed or forced.
Final ROM hard limit: 78,000,000 bytes.
