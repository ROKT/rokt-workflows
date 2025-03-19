# Rokt workflows

This repository hosts Rokt's reusable GitHub workflows that we share across our projects for CI builds.  
It also hosts a [Trunk Plugin](https://docs.trunk.io/cli/configuration/plugins) and associated custom linters.

## Usage

### Workflows

In a child repository, you can reference the shared reusable workflow like this:

```yaml
job-name:
    name: "PR Notification"
    uses: ROKT/rokt-workflows/.github/workflows/oss_pr_opened_notification.yml@main
    secrets:
      gchat_webhook: ${{ secrets.YOUR_SECRET }}
```

Full Github documentation can be found [here](https://docs.github.com/en/actions/sharing-automations/reusing-workflows).


### Trunk Plugin

You can add the plugin to another repository by running:  
`trunk plugins add https://github.com/ROKT/rokt-workflows <ref> --id=rokt-trunk-plugin`

You should then be able to add any custom linter defined in [rokt-trunk-plugin/linters](rokt-trunk-plugin/linters), e.g.:  

`trunk check enable validate-actions-versions`