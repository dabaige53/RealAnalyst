#!/usr/bin/env python3
import argparse
import json
import requests

from _bootstrap import bootstrap_tableau_scripts_path

TABLEAU_SCRIPTS = bootstrap_tableau_scripts_path()

from auth import TableauAuth, get_auth  # type: ignore[import-not-found]


def fetch_metadata(view_luid: str):
    auth = get_auth()
    auth.signin()

    query = """
    query getSheetMetadata($luid: String!) {
      sheets(filter: {luid: $luid}) {
        name
        workbook {
          name
          luid
        }
        datasourceFields {
          name
          __typename
          ... on ColumnField {
            dataType
            description
          }
          ... on CalculatedField {
            dataType
            formula
          }
        }
      }
    }
    """

    variables = {"luid": view_luid}

    endpoint = f"{auth.base_url}/api/metadata/graphql"
    headers = auth.get_headers()

    print(f"[Metadata] Querying GraphQL: {endpoint}")
    resp = requests.post(
        endpoint, json={"query": query, "variables": variables}, headers=headers, timeout=60
    )

    if resp.status_code != 200:
        print(f"Error: {resp.status_code}\n{resp.text}")
        return None

    return resp.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("view_luid")
    args = parser.parse_args()

    result = fetch_metadata(args.view_luid)
    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
