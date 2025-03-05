# Rokt workflows

This repository hosts Rokt's reusable GitHub workflows that we share across our projects for CI builds.

## Usage

In a child repository, you can reference the shared reusable workflow like this:

```yaml
job-name:
    name: "PR Notification"
    uses: ROKT/rokt-workflows/.github/workflows/oss_pr_opened_notification.yml@main
    secrets:
      gchat_webhook: ${{ secrets.YOUR_SECRET }}
```

Full Github documentation can be found [here](https://docs.github.com/en/actions/sharing-automations/reusing-workflows).
