# Trivy ignore policy — package-level exceptions that per-ID allowlisting
# cannot express sanely. Per-ID exceptions stay in .trivyignore.
package trivy

import data.lib.trivy

default ignore := false

# linux-libc-dev ships kernel *headers* for building out-of-tree modules.
# A container runs on the host kernel: nothing in the image loads or
# executes this package, so its CVEs carry no attack surface here — but
# Ubuntu publishes them in large batches, and per-ID allowlisting them
# meant daily .trivyignore churn (seven IDs appeared on 2026-08-05,
# thirteen more on 2026-08-06) for zero security change. Reviewed
# 2026-08-06; revisit if any service starts compiling modules at runtime
# (none does) or if the package gains a runtime component.
ignore {
	input.PkgName == "linux-libc-dev"
}
