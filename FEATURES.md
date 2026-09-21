# Features

This document describes what the XML attributes do. It is a work in progress:
add a section when you add or change a feature.

## Checksum selection: the `sha` attribute

openQA needs the checksum file that OBS publishes next to each asset, for
example `my-DVD.x86_64-Build1.1.iso.sha256`. The `sha` attribute selects the
digest length, `256` or `512`. Set it on a `<flavor>` node. Without the
attribute a flavor uses `256`.

```xml
<flavor name="Tumbleweed-DVD" distri="opensuse" iso="1" folder="*product*"/>
<flavor name="offline-installer|offline-install" distri="opensuse" iso="1" sha="512"/>
```
