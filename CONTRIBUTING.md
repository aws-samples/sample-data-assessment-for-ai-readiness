# Contributing Guidelines

Thank you for your interest in contributing to FORGE. Whether it's a bug report,
new feature, correction, or additional documentation, we greatly value feedback
and contributions from our community.

Please read through this document before submitting any issues or pull requests.

## Reporting Bugs/Feature Requests

Use the GitHub issue tracker to report bugs or suggest features. When filing an
issue, please check existing open and recently closed issues to make sure someone
else hasn't already reported it. Include as much detail as you can: repro steps,
versions, and anything unusual in the environment.

## Security issue notifications

If you discover a potential security issue in this project we ask that you notify
AWS/Amazon Security via our [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/).
Please do **not** create a public GitHub issue for security findings.

## Contributing via Pull Requests

Before sending a pull request, please ensure that:

1. You are working against the latest source on the *main* branch.
2. You check existing open and merged PRs to avoid duplicating effort.
3. Tests pass locally: `pip install -e '.[test]'` then `python3 -m pytest tests/`.
4. Dependencies stay pinned; regenerate `requirements-lock.txt` with
   `pip-compile --generate-hashes requirements.in` if you change them.

## Licensing

See the [LICENSE](LICENSE) file for this project's licensing (MIT-0). We will ask
you to confirm the licensing of your contribution.
