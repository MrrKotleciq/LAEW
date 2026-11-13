# CMake generated artifact dependencies
## Outputs
An OUTPUT custom command defines a build rule for generated files.
Independent targets must not each own the same generated output when they may build concurrently.
Use one custom target to drive shared generation and make consumers depend on it.
## Auxiliary products
Declare secondary generated files with BYPRODUCTS so Ninja knows how to rebuild them when missing.
Relative byproduct paths are interpreted relative to the build tree directory for the source directory.
## Arguments
VERBATIM asks CMake to escape arguments appropriately for the build tool.
Multiple COMMAND entries are not guaranteed to share a stateful shell.
