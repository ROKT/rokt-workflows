# The payment extension ships no consumer rules and its Stripe/Google Pay surface is only reached
# at runtime through the PaymentExtension interface, so without this rule R8 strips most of Stripe
# and both payment-extension packages under-report by megabytes.
-keep class com.rokt.payment.extension.** { *; }
