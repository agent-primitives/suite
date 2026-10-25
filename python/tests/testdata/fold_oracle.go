package main

import (
	"encoding/json"
	"os"
	"unicode/utf8"

	"golang.org/x/text/cases"
)

func main() {
	fold := cases.Fold()
	out := map[string]string{}
	for r := rune(0); r <= utf8.MaxRune; r++ {
		if r >= 0xD800 && r <= 0xDFFF {
			continue
		}
		value := string(r)
		if folded := fold.String(value); folded != value {
			out[value] = folded
		}
	}
	if err := json.NewEncoder(os.Stdout).Encode(out); err != nil {
		panic(err)
	}
}
