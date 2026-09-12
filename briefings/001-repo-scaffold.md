# Briefing 001: Repository scaffold for halo-gauge-experiment

Author: Mausi (master chat)
Executor: Claude Code (CC)
Repository: https://github.com/saschadaemgen/halo-gauge-experiment (private)
Local root: C:\Projects\CYB3RGUN\HUBEN\halo-gauge-experiment

## Goal

Move the files that already sit in the local root into the repository layout, add the documentation files from the scaffold package, configure Git LFS for binary assets, and push four commits.

## Working rules

- Stop at the first failure and report the exact output. Do not improvise.
- Do not edit the content of any .md, .ino, .stl or .png file. This briefing is about placement and Git only.
- No em dashes anywhere in files you create. Use normal hyphens.
- Conventional Commits, one commit per concern, messages given below.

## Step 0: Verify state

```
git remote -v
git status
git lfs version
```

Remote must point to saschadaemgen/halo-gauge-experiment via SSH. Report the branch name. If Git LFS is missing, STOP and report.

List the current root. Expected: five `jig_v5_*.stl`, `jig_v5_sections.png`, `mhg01.png`, `mhgz01.png`, and the unpacked scaffold folder.

## Step 1: Target layout

```
halo-gauge-experiment/
  README.md
  .gitignore
  .gitattributes
  briefings/001-repo-scaffold.md
  docs/
    research/prior-art.md
    method/measurement.md
    log/jig-versions.md
    log/data/.gitkeep
  hardware/
    jig/README.md
    jig/gauge_jig_base.stl
    jig/jig_v5_frame.stl
    jig/jig_v5_slide.stl
    jig/jig_v5_carrier.stl
    jig/jig_v5_led_holder.stl
    jig/jig_v5_rail.stl
    jig/jig_v5_sections.png
    cards/mhg01.png
    cards/mhgz01.png
    cards/README.md
  firmware/probe/halo_gauge_probe.ino
```

Move the existing files with `git mv` where they are already tracked, plain move otherwise. `mhg01.png` is the dial artwork, `mhgz01.png` is the needle artwork.

Create `hardware/cards/README.md` with exactly this content:

```markdown
# Test cards

Source artwork exported from Illustrator, 1:1, dial diameter 20 mm.

- `mhg01.png` dial face without needle
- `mhgz01.png` needle, separate layer

Card format is 100 x 100 mm. The card set (full white, full yellow, nine dial cards with the needle at 0 to 40 MPa in 5 MPa steps) is generated from these two files. Print all cards on the same printer and paper.
```

## Step 2: .gitignore

```
# OS
Thumbs.db
.DS_Store

# Editors
.vscode/
.idea/

# Arduino build output
firmware/**/build/
*.bin
*.elf
```

## Step 3: .gitattributes and LFS

```
*.stl filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
*.jpg filter=lfs diff=lfs merge=lfs -text
*.pdf filter=lfs diff=lfs merge=lfs -text
*.3mf filter=lfs diff=lfs merge=lfs -text
```

Run `git lfs install` once. Because the STL and PNG files may already be committed as plain blobs, run `git lfs migrate import --include="*.stl,*.png" --everything` only if `git log --oneline | wc -l` is greater than 0 and the files appear in history. If the repository has no commits yet, skip the migration. Report which case applied.

## Step 4: Commits

```
chore(repo): add gitignore, gitattributes and LFS tracking
docs: add README, prior art, measurement method and jig version log
feat(hardware): add test jig v5 STL files, base plate and card artwork
feat(firmware): add halo gauge probe sketch for Heltec WiFi LoRa 32 V2
```

Then `git push -u origin <branch>`.

## Report back

1. Branch name and remote
2. Whether LFS migration was needed and its result
3. The four commit hashes and the push result
4. `git ls-files` output

No suggestions for next steps. Those come from the master chat.
