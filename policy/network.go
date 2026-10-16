package policy

import (
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"net/netip"
	"sort"
)

// Closed wire types keep fields from the other profile forbidden, even when null or empty.
type filesystemPolicyWire struct {
	Version              string   `json:"version"`
	DenyWritePaths       []string `json:"denyWritePaths"`
	RequiredCapabilities []string `json:"requiredCapabilities"`
}

type networkPolicyWire struct {
	Version              string       `json:"version"`
	Network              *networkWire `json:"network"`
	RequiredCapabilities []string     `json:"requiredCapabilities"`
}

type networkWire struct {
	EgressAllow []networkEndpointWire `json:"egressAllow"`
}

type networkEndpointWire struct {
	Address  string `json:"address"`
	Protocol string `json:"protocol"`
	// The root strict decoder uses json.Number for numbers in interfaces. Retain
	// the original lexeme so fractions cannot round into an integer through JCS.
	Port any `json:"port"`
}

func decodeSuiteWire(data []byte) (SuitePolicy, error) {
	var fields map[string]json.RawMessage
	if err := decodeStrict(data, &fields); err != nil {
		return SuitePolicy{}, err
	}
	var version string
	if err := json.Unmarshal(fields["version"], &version); err != nil {
		return SuitePolicy{}, fmt.Errorf("policy version: %w", err)
	}
	switch version {
	case SchemaVersion:
		var wire filesystemPolicyWire
		if err := decodeStrict(data, &wire); err != nil {
			return SuitePolicy{}, err
		}
		return SuitePolicy{Version: wire.Version, DenyWritePaths: wire.DenyWritePaths, RequiredCapabilities: wire.RequiredCapabilities}, nil
	case SchemaVersionV2:
		var wire networkPolicyWire
		if err := decodeStrict(data, &wire); err != nil {
			return SuitePolicy{}, err
		}
		network, err := networkFromWire(wire.Network)
		if err != nil {
			return SuitePolicy{}, err
		}
		return SuitePolicy{Version: wire.Version, Network: network, RequiredCapabilities: wire.RequiredCapabilities}, nil
	default:
		return SuitePolicy{}, fmt.Errorf("unsupported policy version %q", version)
	}
}

// DecodeAdministrativePolicyForVersion decodes restrictions for one policy profile.
// In v2 an omitted network is neutral; an explicit empty egressAllow denies all.
func DecodeAdministrativePolicyForVersion(data []byte, version string) (AdministrativePolicy, error) {
	if version == SchemaVersion {
		return DecodeAdministrativePolicy(data)
	}
	if version != SchemaVersionV2 {
		return AdministrativePolicy{}, fmt.Errorf("unsupported administrative policy version %q", version)
	}
	var wire struct {
		Network json.RawMessage `json:"network"`
	}
	if err := decodeStrict(data, &wire); err != nil {
		return AdministrativePolicy{}, fmt.Errorf("decode administrative policy: %w", err)
	}
	if wire.Network == nil {
		return AdministrativePolicy{}, nil
	}
	var network networkWire
	if err := decodeStrict(wire.Network, &network); err != nil {
		return AdministrativePolicy{}, fmt.Errorf("decode administrative network: %w", err)
	}
	decoded, err := networkFromWire(&network)
	if err != nil {
		return AdministrativePolicy{}, fmt.Errorf("administrative: %w", err)
	}
	return AdministrativePolicy{Network: decoded}, nil
}

func networkFromWire(wire *networkWire) (*NetworkPolicy, error) {
	if wire == nil {
		return nil, errors.New("network is required")
	}
	if wire.EgressAllow == nil {
		return nil, errors.New("network egressAllow must be a non-null list")
	}
	if len(wire.EgressAllow) > 4096 {
		return nil, errors.New("too many network egressAllow endpoints")
	}
	endpoints := make([]NetworkEndpoint, len(wire.EgressAllow))
	for i, endpoint := range wire.EgressAllow {
		port, err := networkPort(endpoint.Port)
		if err != nil {
			return nil, fmt.Errorf("network endpoint %d: %w", i, err)
		}
		endpoints[i] = NetworkEndpoint{Address: endpoint.Address, Protocol: endpoint.Protocol, Port: port}
	}
	network := &NetworkPolicy{EgressAllow: endpoints}
	if err := validateNetwork(network); err != nil {
		return nil, err
	}
	return network, nil
}

func networkPort(value any) (int, error) {
	number, ok := value.(json.Number)
	if !ok {
		return 0, errors.New("network port must be an integer from 1 to 65535")
	}
	// Reject out-of-range values before exact parsing, including enormous negative
	// exponents that could otherwise cause unbounded rational allocations.
	approximate, err := number.Float64()
	if err != nil || approximate < 1 || approximate > 65535 {
		return 0, errors.New("network port must be an integer from 1 to 65535")
	}
	// JSON Schema integers include decimal and exponent forms, but not fractions
	// that merely round to an integer in floating-point arithmetic.
	exact, ok := new(big.Rat).SetString(number.String())
	if !ok || !exact.IsInt() {
		return 0, errors.New("network port must be an integer from 1 to 65535")
	}
	return int(exact.Num().Int64()), nil
}

func validateProfileCapabilities(capabilities []string, version string) error {
	if version == SchemaVersion {
		return validateCapabilities(capabilities)
	}
	if len(capabilities) != 1 || capabilities[0] != NetworkEgressAllow {
		return fmt.Errorf("requiredCapabilities must be exactly [%q]", NetworkEgressAllow)
	}
	return nil
}

func validateNetworkProfile(paths []string, network *NetworkPolicy, capabilities []string) error {
	if paths != nil {
		return errors.New("denyWritePaths is not allowed in v2 policy")
	}
	if err := validateNetwork(network); err != nil {
		return err
	}
	return validateProfileCapabilities(capabilities, SchemaVersionV2)
}

func validateNetwork(network *NetworkPolicy) error {
	if network == nil {
		return errors.New("network is required")
	}
	if network.EgressAllow == nil {
		return errors.New("network egressAllow must be a non-null list")
	}
	if len(network.EgressAllow) > 4096 {
		return errors.New("too many network egressAllow endpoints")
	}
	for _, endpoint := range network.EgressAllow {
		address, err := netip.ParseAddr(endpoint.Address)
		if err != nil || !address.Is4() || address.String() != endpoint.Address {
			return errors.New("network address must be a canonical IPv4 literal")
		}
		if endpoint.Protocol != "TCP" {
			return errors.New("network protocol must be TCP")
		}
		if endpoint.Port < 1 || endpoint.Port > 65535 {
			return errors.New("network port must be an integer from 1 to 65535")
		}
	}
	return nil
}

func normalizeEndpoints(endpoints []NetworkEndpoint) []NetworkEndpoint {
	set := make(map[NetworkEndpoint]struct{}, len(endpoints))
	for _, endpoint := range endpoints {
		set[endpoint] = struct{}{}
	}
	out := make([]NetworkEndpoint, 0, len(set))
	for endpoint := range set {
		out = append(out, endpoint)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Address != out[j].Address {
			return out[i].Address < out[j].Address
		}
		return out[i].Port < out[j].Port
	})
	return out
}

func resolveNetwork(s SuitePolicy, a AdministrativePolicy) (EffectivePolicy, error) {
	if a.DenyWritePaths != nil {
		return EffectivePolicy{}, errors.New("administrative denyWritePaths is not allowed in v2 policy")
	}
	endpoints := normalizeEndpoints(s.Network.EgressAllow)
	if a.Network != nil {
		if err := validateNetwork(a.Network); err != nil {
			return EffectivePolicy{}, fmt.Errorf("administrative: %w", err)
		}
		allowed := make(map[NetworkEndpoint]struct{}, len(a.Network.EgressAllow))
		for _, endpoint := range a.Network.EgressAllow {
			allowed[endpoint] = struct{}{}
		}
		intersection := make([]NetworkEndpoint, 0, len(endpoints))
		for _, endpoint := range endpoints {
			if _, ok := allowed[endpoint]; ok {
				intersection = append(intersection, endpoint)
			}
		}
		endpoints = intersection
	}
	return EffectivePolicy{
		Version: SchemaVersionV2, Network: &NetworkPolicy{EgressAllow: endpoints},
		RequiredCapabilities: []string{NetworkEgressAllow},
	}, nil
}
