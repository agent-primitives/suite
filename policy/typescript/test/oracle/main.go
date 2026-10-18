//go:build ignore

// Copyright (c) Microsoft Corporation. Licensed under the MIT License.
// Test-only line protocol. Production TypeScript never invokes Go.
package main

import (
	"bufio"
	"encoding/json"
	"os"

	"github.com/agent-primitives/suite/policy"
)

type request struct {
	Data    []byte                  `json:"data"`
	Payload *policy.ProviderPayload `json:"payload,omitempty"`
}

type response struct {
	Accepted  bool   `json:"accepted"`
	Canonical []byte `json:"canonical,omitempty"`
	Digest    string `json:"digest,omitempty"`
	Verified  bool   `json:"verified"`
}

func main() {
	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 4096), 32<<20)
	writer := json.NewEncoder(os.Stdout)
	for scanner.Scan() {
		var input request
		if err := json.Unmarshal(scanner.Bytes(), &input); err != nil {
			panic(err)
		}
		result := response{}
		decoded, err := policy.DecodeSuitePolicy(input.Data)
		if err == nil {
			result.Accepted = true
			result.Canonical, err = policy.CanonicalBytes(policy.EffectivePolicy(decoded))
			if err != nil {
				panic(err)
			}
			result.Digest = policy.Digest(result.Canonical)
		}
		if input.Payload != nil {
			result.Verified = policy.VerifyPayload(*input.Payload) == nil
		}
		if err := writer.Encode(result); err != nil {
			panic(err)
		}
	}
	if err := scanner.Err(); err != nil {
		panic(err)
	}
}
