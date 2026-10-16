// Copyright (c) Kaimahi contributors. Licensed under the MIT License.
// Package policy defines AgentSuite enforcement policy contracts.
package policy

const (
	SchemaVersion       = "agentsuite.policy/v1"
	SchemaVersionV2     = "agentsuite.policy/v2"
	FilesystemDenyWrite = "filesystem/deny-write/v1"
	NetworkEgressAllow  = "network/egress-allow/v1"
)

// NetworkEndpoint is one literal canonical IPv4 address, TCP protocol, and explicit port.
type NetworkEndpoint struct {
	Address  string `json:"address"`
	Protocol string `json:"protocol"`
	Port     int    `json:"port"`
}

// NetworkPolicy is an exact endpoint allow ceiling. An explicit empty list denies all egress.
type NetworkPolicy struct {
	EgressAllow []NetworkEndpoint `json:"egressAllow"`
}

// SuitePolicy is strict user intent: filesystem restrictions in v1, network restrictions in v2.
type SuitePolicy struct {
	Version              string         `json:"version"`
	DenyWritePaths       []string       `json:"denyWritePaths,omitempty"`
	Network              *NetworkPolicy `json:"network,omitempty"`
	RequiredCapabilities []string       `json:"requiredCapabilities,omitempty"`
}

// AdministrativePolicy adds mandatory restrictions; composition never removes user restrictions.
type AdministrativePolicy struct {
	DenyWritePaths []string       `json:"denyWritePaths,omitempty"`
	Network        *NetworkPolicy `json:"network,omitempty"`
}

// EffectivePolicy is normalized, fully composed policy.
type EffectivePolicy struct {
	Version              string         `json:"version"`
	DenyWritePaths       []string       `json:"denyWritePaths,omitempty"`
	Network              *NetworkPolicy `json:"network,omitempty"`
	RequiredCapabilities []string       `json:"requiredCapabilities"`
}

// ProviderPayload carries authoritative canonical bytes. Consumers must preserve PolicyBytes.
type ProviderPayload struct {
	Version              string   `json:"version"`
	PolicyBytes          []byte   `json:"policyBytes"`
	PolicyDigest         string   `json:"policyDigest"`
	RequiredCapabilities []string `json:"requiredCapabilities"`
}
