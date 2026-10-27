# Third-party notices

## 1. This repository — MIT

Copyright (c) 2026 Vincent GAUTIER. The source code in this repository is released
under the MIT license (see [LICENSE](LICENSE)).

## 2. Models used to produce this code — not distributed

Parts of this code were written with the assistance of **`deepseek-v4.1-flash`**
(DeepSeek), served locally by a Strata engine. **No model weights, checkpoints or
derivatives are included in, or redistributed with, this repository.**

The DeepSeek model license (the `LICENSE-MODEL` file shipped with DeepSeek's open
model repositories) is explicit about outputs:

> Except as set forth herein, DeepSeek claims no rights in the Output You generate
> using the Model. You are accountable for the Output you generate and its
> subsequent uses.

Consequences for this project:

- the license governs **the model** (weights, use, redistribution), not the licence
  you choose for code you wrote with it;
- its **use-based restrictions** (Attachment A of that license) constrain how the
  model may be *used*, not how the generated code may be *licensed*;
- publishing this code under MIT therefore does not conflict with that license, and
  no DeepSeek license text has to be bundled here since nothing of the model is
  redistributed.

Attribution is given in [docs/CREDITS.md](docs/CREDITS.md) as a matter of
professional credit, not as a license obligation.

**Trademarks** — “DeepSeek” and the model names are trademarks of their respective
owners. They are used here descriptively (nominative use). This project is not
affiliated with, sponsored or endorsed by DeepSeek or Nous Research.

**Caveat for downstream users** — whoever is accountable for model output is the
person who runs it. As with any AI-assisted code, review before shipping, and keep
the usual diligence on third-party snippets.

## 3. Embedded CA bundle

`assets/cacert.pem` is the [certifi](https://github.com/certifi/python-certifi) root
bundle (MPL-2.0), which packages Mozilla's public root store. It is embedded in the
executable so that `https://` works on machines with an incomplete system trust store.

## 4. Configuration formats

The file shapes written by this tool come from the projects themselves — opencode,
Hermes Agent (Nous Research) and dsh (DeepSeek). No code from those projects is
included here; only their configuration *schema* is described in
[docs/HARNESS-FILES.md](docs/HARNESS-FILES.md).
