// Test-only Go oracle for strict codec acceptance and canonical byte parity.
package main

import (
	"bufio"
	"encoding/json"
	"os"

	"github.com/agent-primitives/suite/core"
)

func main() {
	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 4096), 8<<20)
	encoder := json.NewEncoder(os.Stdout)
	for scanner.Scan() {
		var request struct {
			Input  string
			Target string
		}
		if err := json.Unmarshal(scanner.Bytes(), &request); err != nil {
			panic(err)
		}
		var target any = new(any)
		if request.Target == "descriptor" {
			target = new(core.Descriptor)
		}
		err := core.Unmarshal([]byte(request.Input), target)
		var canonical []byte
		if err == nil {
			canonical, err = core.Marshal(target)
		}
		if err := encoder.Encode(struct {
			Valid     bool
			Canonical string
		}{err == nil, string(canonical)}); err != nil {
			panic(err)
		}
	}
	if err := scanner.Err(); err != nil {
		panic(err)
	}
}
