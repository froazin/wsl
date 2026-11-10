# Prints the version every manifest shares, which the release is tagged with. Run it with -n and every manifest's path.
# Fails when a manifest has no version string, or when the manifests' versions differ. make build checks the format.

[inputs | {file: input_filename, version: (if type == "object" then .version else null end)}]
| (map(select(.version | type != "string")) | .[0] // empty
    | error("\(.file): field \"version\" must be a string, such as \"0.0.1\"."))
, (if (map(.version) | unique | length) == 1 then
     .[0].version
   else
     error("Every manifest must have the same version, but \(map("\(.file) has \(.version)") | join(", ")).")
   end)
