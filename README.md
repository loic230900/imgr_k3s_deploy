# imgr — Cloud-native image hosting on k3s

A small image-hosting platform deployed end-to-end on a Kubernetes cluster (k3s) provisioned from custom OpenStack images, with full CI/CD, Infrastructure as Code, and security scanning. Built for the M1 SIRIS "Cloud & Virtualization" course.

## What's inside

The repo covers the full delivery chain for a containerized web app:

| Layer | Stack |
|------|-------|
| **Web frontend** | TypeScript, served from a container |
| **API / worker** | Python |
| **Containerization** | Docker + docker-compose for local dev |
| **Cluster** | k3s (lightweight Kubernetes) on OpenStack VMs |
| **K8s manifests** | Deployments, Services, Ingress in `k8s/` |
| **Provisioning** | Ansible playbooks for cluster bootstrap and app deploy |
| **VM images** | Packer templates for OpenStack base images |
| **CI/CD** | GitLab CI pipeline with linting, build, and deploy stages |
| **Security** | Trivy container scanning, ansible-lint, yamllint, pre-commit hooks |

## A note on the CI/CD pipeline

The `.gitlab-ci.yml` pipeline in this repository was designed to run on a **GitLab** instance, not GitHub. The pipeline references private runners, a GitLab container registry, and deploy targets that were configured for the original `git.unistra.fr` project where this work was developed and graded.

**On GitHub, the pipeline will not execute** — GitHub Actions ignores `.gitlab-ci.yml`, and even if it didn't, the runners, registry, and secrets referenced are not reachable from here. The file is kept in the repo as a reference: it documents the build, lint, security-scan, and deploy stages that ran during the project.

To see the pipeline in action you would need to:
- Re-host the repo on a GitLab instance
- Register a runner with the required tags
- Configure the GitLab CI/CD variables for the container registry and target cluster

The runbook in `GUIDE_EXPLOITATION_MAINTENANCE.md` describes the deploy targets in more detail.
## Repo layout

```
.
├── api/                      # Python backend / worker
├── web/                      # TypeScript frontend
├── docker/                   # Dockerfiles
├── k8s/                      # Kubernetes manifests
├── ansible/                  # Provisioning playbooks
├── cicd/                     # CI/CD helpers
├── packer/                   # OpenStack image build templates
├── docker-compose.yml        # Local dev stack
├── .gitlab-ci.yml            # CI pipeline
├── .pre-commit-config.yaml   # Hooks: ansible-lint, yamllint, trivy
└── GUIDE_EXPLOITATION_MAINTENANCE.md   # Ops runbook
```

Each subdirectory has its own README with detailed instructions.

## Highlights

- **Reproducible cluster images** — Packer templates produce versioned OpenStack images, so cluster bootstrap is deterministic.
- **GitOps-style CI/CD** — every push runs linting, security scans, builds, and (on `main`) deploys.
- **Operations runbook** — `GUIDE_EXPLOITATION_MAINTENANCE.md` documents day-2 workflow.
- **Pre-commit hooks** prevent broken YAML, unsafe Ansible patterns, or vulnerable container layers from reaching `main`.

## Local development

```bash
docker compose up --build
```

Web frontend at `http://localhost:<port>`, API behind it.

## Deploy to a cluster

Full deploy procedure (provisioning, secret management, rolling updates) is in `GUIDE_EXPLOITATION_MAINTENANCE.md`. From a workstation with cluster credentials configured:

```bash
ansible-playbook ansible/deploy.yml
```

Cluster credentials and OpenStack/AWS configuration are intentionally not committed — see the runbook for how to set them up locally.

## What I learned

- End-to-end Kubernetes operations: provisioning, image building, ingress, secrets, rolling updates.
- Practical CI/CD on a real cluster — pipeline design, security scanning, deploy gates.
- IaC discipline: keeping infrastructure changes reviewable like application code.

## Authors

Team project. See `git shortlog -sne` for individual contribution breakdown.

## License

See [`LICENSE`](LICENSE). Apache 2.0.
