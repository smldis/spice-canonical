# Extracting a Canonical Netlist

The extractor turns an Eldo or ngspice deck into
[the canonical representation](representation.md). It resolves what it can
structurally, and says out loud — as a diagnostic, never as a guess — what it
could not.

The implementation is `spice_canonical.canonical_netlist`.

## Python API

```python
from spice_canonical.canonical_netlist import from_file

netlist = from_file("input.spi", top_name="TOP", spice_format="eldo")
print(netlist.render())

for diagnostic in netlist.diagnostics:
    print(f"{diagnostic.source}:{diagnostic.line}: {diagnostic.message}")
```

`from_file` expands includes relative to each file that declares them.
`from_text` parses a single string; it has no base directory and therefore
leaves include directives unexpanded. Use `from_file` when resolving a
multi-file deck.

Both return a `CanonicalNetlist`, which is plain data rather than a parser
handle:

| Attribute | What it holds |
| --- | --- |
| `top` | the root `Circuit` |
| `subcircuits` | one `Circuit` per `.SUBCKT`, in declaration order |
| `diagnostics` | a `Diagnostic` per non-fatal omission or assumption |

A `Circuit` carries `name`, `pins`, `devices`, and
`parameter_defaults: tuple[Parameter, ...] = ()`. The optional final field keeps
existing three-argument constructors usable. Each `Parameter` has a `name` and
raw, unevaluated `value`; defaults retain declaration order and spelling.
A `Device` carries `name`, `type`, `connections`, and `parameters`; subcircuit
instance parameters remain explicit overrides. `render()` produces the tabular
text, including a `PARAMETER_DEFAULTS` table for definitions with defaults.
`normalize_device_types` preserves circuit defaults.

Header defaults accept assignments with or without `PARAMS:` (also `PARAM:`),
spaces on either side of `=`, leading `+` continuations, and quoted or grouped
expressions. Expressions containing whitespace or comparison assignments must
be quoted or grouped. Missing values, stray tokens after defaults begin, and
unbalanced quotes or groups raise `CanonicalParseError` with the declaration's
logical starting line; they are not silently omitted. Before any assignment or
parameter marker, bare tokens are pins, so a missing `=` cannot always be
inferred. Expression validity and duplicate-name precedence are left to the
simulator.

Defaults are not evaluated, substituted into device expressions, or expanded
into instances. Global `.PARAM` semantics and model-body interpretation remain
deferred and omitted from canonical data (the existing `.MODEL` name/type
refinement still applies). Use `from_canonical_file("canonical.txt")` or
`from_canonical_text(text)` from the same module to reload saved custom tables.
They preserve diagnostics and black-box interfaces without reopening SPICE files.

A netlist that is structurally inconsistent rather than merely incomplete raises
`CanonicalParseError` — a duplicate device name within one circuit, an instance
connecting the wrong number of nets to a known subcircuit, a nested `.SUBCKT`, a
`.ENDS` outside a subcircuit, or an unterminated `.CONTROL` block.

## Command line

```bash
spice-canonical input.spi --output canonical.txt
spice-canonical input.spi --top-name CHIP
spice-canonical input.spi --strict
spice-canonical input.cir --format ngspice --strict
spice-canonical input.cir --device-type-map device-types.json
```

Without `--output`, the representation is written to standard output. Warnings
are written to standard error. `--strict` returns a failure when any statement
cannot be completely resolved. A `CanonicalParseError`, an unreadable input, or
malformed JSON exits with status 2 and an `error:` line.

## Supported extraction

The parser handles:

- case-insensitive SPICE directives and names while preserving source spelling;
- `.SUBCKT`/`.ENDS`, declaration parameters, and named subcircuit calls;
- `.MODEL` declarations for device-type refinement;
- leading `+` continuation lines;
- full-line `*` and `//` comments and inline `$` or whitespace-delimited `//`
  comments;
- grouped quoted, parenthesized, bracketed, and braced expressions;
- common `R`, `C`, `L`, `V`, `I`, `B`, `D`, `M`, `J`, `Q`, `E`, `F`, `G`,
  `H`, `S`, `T`, `O`, `W`, `K`, and `X` devices.
- recursive `.INCLUDE` and `.INC` expansion when using `from_file` or the CLI.

A device's type comes from its `.MODEL` declaration where one applies, so an `M`
device using a model declared `NMOS` is typed `nmos` rather than `mosfet`. When
the model is not declared in the expanded deck, the generic type is kept.

Pass `spice_format="ngspice"` to the Python API, or `--format ngspice` to the
CLI, for ngspice decks. Ngspice mode additionally handles:

- the first physical line of the root deck as its title;
- semicolon end-of-line comments;
- `.CONTROL`/`.ENDC` blocks without treating control commands as devices;
- model-bin families such as `nch.1`, `nch.2`, instantiated as `nch`;
- `U` uniform distributed RC lines and `Z` MESFET devices.

The title rule applies only to the root deck. The first line of an included file
is retained because `.INCLUDE` has textual insertion semantics.

Unsupported proprietary device prefixes are retained in the device table as
`unresolved`, with their unparsed text in `raw` and a diagnostic. The extractor
does not invent terminal names because doing so would create false graph edges.
Variable-topology XSPICE code models and coupled multiconductor lines are
currently retained this way.

## Includes and boundaries

File-based extraction treats includes as textual insertion. Relative paths are
resolved from the directory containing each include directive. Quoted paths,
home-directory paths, and environment variables are supported. Nested includes
are expanded recursively in simulator order. As a result:

- top-level devices from included files are concatenated into the parent circuit;
- included `.SUBCKT` definitions receive their own canonical tables;
- included `.MODEL` declarations participate in device-type resolution;
- instances in any expanded file can resolve subcircuits declared in another;
- missing files and include cycles are skipped with source-qualified diagnostics.

Repeated non-cyclic includes are expanded each time, matching textual include
semantics. Duplicate resulting subcircuits or device names are therefore reported
as structural errors. `.LIB` section selection and simulator-specific library
search paths are not expanded; a `.LIB` file is an opaque model-library
boundary.

Some includes should stay opaque even when they are readable — a vendor model
file is thousands of lines that contribute no connectivity. `stop_include`, or
`--stop-include` repeated on the command line, takes a glob matched against
either the include's basename or its resolved path, and leaves matching files
unexpanded.

Instances that cross such a boundary have no declaration to bind against, so
their terminals retain positional names `@1`, `@2`, etc., with an explicit
`BlackBox(cell, "positional")` marker and a diagnostic about unavailable formal
pin names. Supplying pin names creates `BlackBox(cell, "named")` and binds named
connections without reading the library:

```python
netlist = from_file(
    "top.sp",
    stop_include=["vendor-*.inc"],
    external_subcircuits={"nch": ["d", "g", "s", "b"]},
)
```

The CLI equivalent is `--external-subcircuits interfaces.json`, whose JSON maps
each opaque subcircuit name to an array of pin names:

```json
{"nch": ["d", "g", "s", "b"]}
```

A subcircuit actually declared in the expanded deck always wins over an external
signature of the same name.

## Normalizing library device types

Library primitives represented as opaque subcircuit instances can optionally be
normalized before rendering. The pass is activated explicitly with
`device_type_map` in the Python API or `--device-type-map` in the CLI. Its JSON
form maps source type names to canonical type names:

```json
{
  "sky130_fd_pr__nfet_01v8": "nmos",
  "sky130_fd_pr__pfet_01v8": "pmos"
}
```

Matching is case-insensitive. A normalized device retains its original library
name in the `source_type` parameter. With no map, extraction preserves existing
device types exactly as before. The same pass is available on an already-parsed
netlist as `normalize_device_types`.

## Verifying against real ngspice examples

The unit includes a networked compatibility verifier:

```bash
python scripts/verify_ngspice_corpus.py
```

It downloads three checksum-pinned examples from the official ngspice repository,
runs each one through an installed `ngspice` in batch mode, then requires a strict,
diagnostic-free canonical extraction:

- [`gain_stage.cir`](https://github.com/ngspice/ngspice/blob/master/examples/various/gain_stage.cir)
- [`inv-meas-tran-control.sp`](https://github.com/ngspice/ngspice/blob/master/examples/measure/inv-meas-tran-control.sp)
- [`ltra1_1_line.sp`](https://github.com/ngspice/ngspice/blob/master/examples/TransmissionLines/ltra1_1_line.sp)

Normal unit tests remain offline. A small local integration test runs ngspice when
the executable is available and otherwise skips only that simulator invocation.

Which further netlists are worth pulling into that corpus, and what each one
would prove, is surveyed in
[the integrated-circuit netlist corpus](netlist-corpus.md).

## Unavailable libraries and models

Extraction can retain available structure without a complete simulator deck:

| Input condition | Existing extraction behavior |
| --- | --- |
| Missing root file | Raises an I/O error; there is no input to extract. |
| Missing `.include` file | Continues with a diagnostic naming the resolved missing path and the including file/line. |
| `stop_include` match or `.LIB` | Deliberately leaves the boundary unexpanded; does not check whether that library exists or emit a missing-file diagnostic. |
| Undefined X target | Retains target type, positional `@N` connections, raw overrides and `BlackBox(cell, "positional")`; emits a diagnostic and supplies no guessed formal names. |
| Supplied external subcircuit signature | Binds actual nets to supplied formal pins, checks arity and marks `BlackBox(cell, "named")`; supplies no internal definition. This option belongs to `from_file`. |
| Undeclared MOS/diode model | Retains syntax-defined terminal roles, the model identifier and raw parameters, using generic `mosfet`/`diode` type. Does not infer polarity or model contents. |
| Undeclared BJT model | Uses generic `bjt`; see the terminal-count limitation below. |
| Malformed represented structure | Existing structural checks still apply, including duplicate declarations/devices and known subcircuit arity mismatch. |

Unknown model semantics are different from a missing file: the parser does not
validate model availability, and no diagnostic is emitted merely because a
MOS/diode model declaration is absent. An intentionally opaque library may contain
that declaration. Neither a diagnostic-free extraction nor available terminal
roles establish electrical equivalence or a runnable simulation.

BJT syntax permits three or four terminals. A recognized model identifier locates
the model token. Without one, exactly four positional tokens after the device name
supply the three terminal nets and model identifier; named parameters do not make
that split ambiguous. With additional positional tokens, extraction cannot distinguish
a fourth terminal from a model followed by arguments. It now emits an `unresolved`
device with no connections, retaining every token after the name in `Parameter("raw",
...)` and a source-qualified `ambiguous BJT terminal/model boundary` diagnostic.
For example, `Q1 c b e substrate MissingModel area=2` preserves
`c b e substrate MissingModel area=2` as raw text without assigning a substrate role
or model identity. Available siblings still extract normally. Raw token content is
retained with normalized spacing, not as a byte-for-byte source-line serializer.

Compatibility change: this ambiguous case previously guessed three terminals and
split `substrate` / `MissingModel` into model / arguments. Consumers now receive the
existing unresolved-device representation instead. Unambiguous undeclared-model
three-terminal BJTs and recognized-model four-terminal BJTs retain their prior
behavior. Undeclared-model three-terminal devices with extra positional arguments
also remain unresolved until their split can be established; no new dialect
heuristic is introduced.

`--strict` deliberately exits 2 when extraction emits diagnostics, including
missing includes, undefined X targets and ambiguous BJT syntax. It does not reject
all absent model declarations or intentional boundaries. Non-strict extraction is
the API's normal behavior. No library is fetched automatically.
