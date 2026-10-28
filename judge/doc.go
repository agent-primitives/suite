// Package judge implements the optional agentsuite-judge-producer-v1/1.0.0
// companion profile: exact Chat request production, strict original-envelope
// decoding and two-score verification. It does not change the Suite storage
// specification or the agentsuite-double-score-v1 evidence policy.
//
// Trusted consumers own routes, credentials, content admission, budgets,
// dispatch, independent call identities, retention and safe diagnostics. Apply
// credential-echo and other runtime content checks before retaining raw data or
// invoking this pure decoder. Neither DecodeResponse nor Verify performs those
// checks, authenticates model identity or proves two calls were executed.
//
// Errors are payload-free. Sample.Reasoning is untrusted transient content;
// Result contains no reasoning. A successful pure result is not sufficient
// authority for qualification, publication or deployment.
package judge
