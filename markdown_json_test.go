package agentsuite

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

// TestMarkdownJSONExamples catches unparseable fences and schema-invalid complete
// documents. Fragments must be explicitly marked; an unknown document type fails
// rather than quietly losing schema coverage. Put <!-- json-example: partial -->
// immediately before a fragment's fence and label the excerpt in visible prose.
func TestMarkdownJSONExamples(t *testing.T) {
	mediaSchemas := map[string]string{
		MediaTypeSuite:                   "suite.schema.json",
		MediaTypeAgent:                   "agent.schema.json",
		MediaTypeToolProvider:            "tool-provider.schema.json",
		MediaTypeComposition:             "composition.schema.json",
		MediaTypeToolProviderComposition: "tool-provider-composition.schema.json",
		MediaTypeBuildProfile:            "build-profile.schema.json",
		MediaTypeRuntimeProfile:          "runtime-profile.schema.json",
		MediaTypeEvaluationIndex:         "eval-index.schema.json",
		MediaTypeEvaluationCase:          "eval-case.schema.json",
		MediaTypeEvaluationEvidence:      "eval-evidence.schema.json",
	}
	count := 0
	err := filepath.WalkDir(".", func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			// Ignore version-control metadata and generated dependency/build trees,
			// not source Markdown (including hidden contributor documentation).
			if entry.Name() == ".git" || entry.Name() == "node_modules" ||
				filepath.ToSlash(path) == "docs/.vitepress/dist" ||
				filepath.ToSlash(path) == "docs/.vitepress/cache" {
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.EqualFold(filepath.Ext(path), ".md") {
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		fences, err := scanMarkdownJSON(string(data))
		if err != nil {
			return fmt.Errorf("%s: %w", path, err)
		}
		for _, fence := range fences {
			count++
			t.Run(fmt.Sprintf("%s:%d", filepath.ToSlash(path), fence.line), func(t *testing.T) {
				raw, annotation := fence.raw, fence.annotation
				value, err := decodeMarkdownJSON(raw)
				if err != nil {
					t.Fatalf("invalid JSON: %v", err)
				}
				object, _ := value.(map[string]any)
				media, _ := object["mediaType"].(string)
				version, _ := object["version"].(string)
				_, hasSchemaVersion := object["schemaVersion"]
				_, hasMediaType := object["mediaType"]
				isDocument := hasSchemaVersion || hasMediaType || strings.HasPrefix(version, "agentsuite.policy/")
				if annotation == "<!-- json-example: partial -->" {
					if isDocument {
						t.Fatal("document discriminator present: validate the complete example, do not mark it partial")
					}
					return
				}
				if annotation == "<!-- json-example: oci-empty-config -->" {
					if raw != "{}" {
						t.Fatal("OCI empty config must contain exactly {}")
					}
					return
				}
				if media == MediaTypeToolProviderCatalog {
					// There is no standalone catalog reference schema. Check the
					// §9.1 envelope with the existing shared reference definition,
					// requiring exact versions rather than exempting this document.
					catalogSchema := compileReferenceSchemaJSON(t, []byte(`{
					  "type": "object", "additionalProperties": false,
					  "required": ["schemaVersion", "mediaType", "toolProviders"],
					  "properties": {
					    "schemaVersion": {"const": "1.0.0-draft"},
					    "mediaType": {"const": "application/vnd.agentsuite.tool.provider.catalog.v1+json"},
					    "toolProviders": {"type": "array", "items": {"allOf": [
					      {"$ref": "https://suite.agent-primitives.dev/schema/v0.5/suite.schema.json#/$defs/ref"},
					      {"required": ["version"], "properties": {"version": {
					        "$ref": "https://suite.agent-primitives.dev/schema/v0.5/suite.schema.json#/$defs/version"
					      }}}
					    ]}}
					  }
					}`))
					validateSchemaJSON(t, catalogSchema, raw, true)
					return
				}
				name := mediaSchemas[media]
				if !hasMediaType && !hasSchemaVersion && version == "agentsuite.policy/v2" {
					name = "policy-v2.schema.json"
				}
				if name == "" {
					t.Fatalf("no schema mapping for example (mediaType=%q, version=%q); add a mapping or explicitly label a genuine fragment", media, version)
				}
				validateSchemaJSON(t, compileReferenceSchema(t, name), raw, true)
			})
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if count == 0 {
		t.Fatal("no Markdown JSON fences found")
	}
	t.Logf("checked %d JSON fences", count)
}

func decodeMarkdownJSON(raw string) (any, error) {
	var value any
	err := Unmarshal([]byte(raw), &value)
	return value, err
}

type markdownJSONFence struct {
	line            int
	raw, annotation string
}

var markdownListPrefix = regexp.MustCompile(`^(?:[-+*]|[0-9]{1,9}[.)])[ \t]+`)

func scanMarkdownJSON(markdown string) ([]markdownJSONFence, error) {
	var fences []markdownJSONFence
	lines := strings.Split(markdown, "\n")
	for i := 0; i < len(lines); i++ {
		line := strings.TrimSpace(lines[i])
		quoteDepth := 0
		inList := false
		for {
			if strings.HasPrefix(line, ">") {
				quoteDepth++
				line = strings.TrimSpace(line[1:])
			} else if prefix := markdownListPrefix.FindString(line); prefix != "" {
				inList = true
				line = strings.TrimSpace(line[len(prefix):])
			} else {
				break
			}
		}
		if !strings.HasPrefix(line, "```") && !strings.HasPrefix(line, "~~~") {
			continue
		}
		marker := line[0]
		width := 0
		for width < len(line) && line[width] == marker {
			width++
		}
		info := strings.Fields(line[width:])
		isJSON := len(info) > 0 && strings.EqualFold(info[0], "json")
		if isJSON && inList {
			return nil, fmt.Errorf("line %d: unsupported list-container JSON fence; put the fence on a separate line", i+1)
		}
		start := i
		var content []string
		for i++; i < len(lines); i++ {
			text, matches := stripMarkdownQuote(lines[i], quoteDepth)
			if !matches {
				if isJSON {
					return nil, fmt.Errorf("line %d: JSON fence requires %d blockquote prefixes", i+1, quoteDepth)
				}
				// The quote container ended. Let the outer loop scan this line.
				i--
				break
			}
			close := strings.TrimSpace(text)
			if len(close) >= width && strings.Trim(close, string(marker)) == "" {
				break
			}
			if isJSON {
				content = append(content, text)
			}
		}
		if !isJSON {
			continue
		}
		if i == len(lines) {
			return nil, fmt.Errorf("line %d: unclosed JSON fence", start+1)
		}
		fence := markdownJSONFence{line: start + 1, raw: strings.Join(content, "\n")}
		for j := start - 1; j >= 0; j-- {
			text, matches := stripMarkdownQuote(lines[j], quoteDepth)
			if !matches {
				break
			}
			if text = strings.TrimSpace(text); text != "" {
				fence.annotation = text
				break
			}
		}
		fences = append(fences, fence)
	}
	return fences, nil
}

// Strip only the opening fence's quote depth. Unexpected container syntax in a
// detected JSON block must fail, not silently remove the example from coverage.
func stripMarkdownQuote(line string, depth int) (string, bool) {
	for range depth {
		line = strings.TrimLeft(line, " \t")
		if !strings.HasPrefix(line, ">") {
			return "", false
		}
		line = strings.TrimPrefix(line[1:], " ")
	}
	return line, true
}

func TestScanMarkdownJSONRejectsListOpeners(t *testing.T) {
	for _, prefix := range []string{"- ", "+ ", "* ", "1. ", "2) ", "- 1. ", "> - ", "- > "} {
		t.Run(prefix, func(t *testing.T) {
			markdown := "```json\n{}\n```\n" + prefix + "```json\n  {broken}\n  ```"
			_, err := scanMarkdownJSON(markdown)
			if err == nil || !strings.Contains(err.Error(), "line 4: unsupported list-container JSON fence") {
				t.Fatalf("expected explicit rejection of the list JSON fence, got %v", err)
			}
		})
	}
}

func TestScanMarkdownJSONAfterQuoteEnds(t *testing.T) {
	markdown := "```json\n{}\n```\n> ```text\n> example\n```json\n{broken}\n```"
	fences, err := scanMarkdownJSON(markdown)
	if err != nil {
		t.Fatal(err)
	}
	if len(fences) != 2 {
		t.Fatalf("found %d JSON fences, want 2", len(fences))
	}
	for i, wantValid := range []bool{true, false} {
		_, err := decodeMarkdownJSON(fences[i].raw)
		if valid := err == nil; valid != wantValid {
			t.Fatalf("fence %d: JSON validity = %v, want %v; content: %q", i, valid, wantValid, fences[i].raw)
		}
	}
}

func TestScanMarkdownJSON(t *testing.T) {
	for _, test := range []struct {
		name, markdown string
		count          int
		valid, wantErr bool
	}{
		{"plain", "```json\n{}\n```", 1, true, false},
		{"plain invalid", "```json\n{broken}\n```", 1, false, false},
		{"duplicate document version", "```json\n{\"version\":\"agentsuite.policy/v1\",\"version\":\"agentsuite.policy/v2\",\"network\":{\"egressAllow\":[]},\"requiredCapabilities\":[\"network/egress-allow/v1\"]}\n```", 1, false, false},
		{"highlighted invalid", "```json {1}\n{broken}\n```", 1, false, false},
		{"highlighted valid", "```JSON\t{1}\n{}\n```", 1, true, false},
		{"quoted invalid", "> ```json\n> {broken}\n> ```", 1, false, false},
		{"nested quote highlighted", "> > ~~~json {1}\n> > {}\n> > ~~~", 1, true, false},
		{"non-JSON outer fence", "````text\n```json\n{broken}\n```\n````", 0, false, false},
		{"quoted non-JSON outer fence", "> ````text\n> ```json\n> {broken}\n> ```\n> ````", 0, false, false},
		{"JSON after non-JSON outer fence", "````text\n```json\n{broken}\n```\n````\n```json\n{}\n```", 1, true, false},
		{"unclosed highlighted", "```json {1}\n{}", 0, false, true},
		{"missing quote prefix", "> ```json\n{}\n> ```", 0, false, true},
	} {
		t.Run(test.name, func(t *testing.T) {
			fences, err := scanMarkdownJSON(test.markdown)
			if (err != nil) != test.wantErr {
				t.Fatalf("error = %v, want error = %v", err, test.wantErr)
			}
			if len(fences) != test.count {
				t.Fatalf("found %d JSON fences, want %d", len(fences), test.count)
			}
			for _, fence := range fences {
				_, err := decodeMarkdownJSON(fence.raw)
				if valid := err == nil; valid != test.valid {
					t.Fatalf("JSON validity = %v, want %v; content: %q", valid, test.valid, fence.raw)
				}
			}
		})
	}
}
