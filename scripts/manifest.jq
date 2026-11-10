# Checks one manifest, read with --slurp, against the rules the build relies on, which schemas/manifest.schema.json also
# gives editors. Prints one line for each rule the manifest breaks, and nothing when it keeps them all.
#
# The patterns use \A and \z, because jq's ^ and $ also match at a newline, where the schema's patterns don't.

def semver:
  test("\\A(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)(\\.(0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?(\\+([0-9A-Za-z-]+(\\.[0-9A-Za-z-]+)*))?\\z");

def fragment_name:
  type == "string" and test("\\A[a-z][a-z0-9]*(-[a-z0-9]+)*\\z");

["version", "description", "fragments"] as $fields
| if length != 1 or (.[0] | type) != "object" then
    "The manifest must hold one JSON object."
  else
    .[0] |
    (keys - $fields | .[] | "Unknown field \(tojson). A manifest has only \($fields[:-1] | join(", ")) and \($fields[-1])."),
    ($fields - keys | .[] | "Missing field \(tojson)."),
    (select(has("version") and ((.version | type) != "string" or (.version | semver | not)))
      | "Field \"version\" is \(.version | tojson), which isn't a Semantic Versioning version without a v, such as \"0.0.1\"."),
    (select(has("description") and ((.description | type) != "string" or .description == ""))
      | "Field \"description\" must be a string that isn't empty."),
    (select(has("fragments")) | .fragments
      | if type != "array" or length == 0 then
          "Field \"fragments\" must be a list of at least one fragment name."
        else
          (.[] | select(fragment_name | not)
            | "Field \"fragments\" lists \(tojson), which isn't a fragment name, such as \"github-cli\"."),
          (map(select(fragment_name)) | group_by(.) | .[] | select(length > 1)
            | "Field \"fragments\" lists \(.[0] | tojson) more than once. List each fragment once.")
        end)
  end
