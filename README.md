# Balena Nodel

A reusable, multi-architecture Nodel container for Balena projects. It pins and
verifies a Nodel release, persists Nodel data, and installs a managed node with
actions to reboot or shut down a Balena device and capture its browser display.

The managed recipe is refreshed from the image at every container start. Other
nodes, recipes, and configuration under `/var/lib/nodel` remain persistent.
At startup, ownership of that volume is reconciled to the unprivileged `nodel`
user so volumes created by older root-running images continue to work. The
managed node's name is tracked in the volume; changing `NODEL_NODE_NAME` moves
that node to its new name instead of leaving the old recipe active.

## Use from another Balena project

Add this repository as a submodule:

```sh
git submodule add https://github.com/ACMILabs/balena-nodel.git nodel
```

Then add Nodel to the project's Compose file:

```yaml
services:
  nodel:
    build: ./nodel
    restart: always
    network_mode: host
    labels:
      io.balena.features.supervisor-api: '1'
    volumes:
      - nodel-data:/var/lib/nodel

  browser:
    # The screenshot action calls the browser management API on this host port.
    ports:
      - "5011:5011"

volumes:
  nodel-data:
```

Balena supplies `BALENA_DEVICE_NAME_AT_INIT`, which becomes the managed node's
name. Set `NODEL_NODE_NAME` to override it. `NODEL_INTERFACE` can optionally pin
Nodel discovery to one network interface; automatic discovery is the default.
Set `BROWSER_SCREENSHOT_URL` if the browser API is not available at
`http://127.0.0.1:5011/screenshot`.

The power actions require the Supervisor API label. The screenshot action
requires a compatible Balena browser service with its management port published
at host port 5011. The managed node also publishes the device's detected MAC
addresses under **Network Info**, making it easier to configure a Wake-on-LAN
node hosted on another always-on Nodel device.

### Optional Wake-on-LAN node

Set `NODEL_WOL_NODE_NAME` to install a separate Wake-on-LAN node:

```yaml
services:
  nodel:
    environment:
      NODEL_WOL_NODE_NAME: Gallery PC Wake-on-LAN
```

Configure its MAC address in the Nodel parameters UI. The broadcast address,
UDP port (9999 by default), and packet count are also configurable.

The Wake-on-LAN node controls a remote computer reachable from this Nodel host.
It cannot wake the Balena device running the container after that device has
powered off. Run Nodel on an always-on controller when the Balena device itself
is the Wake-on-LAN target.

The supplied recipe's VNC monitoring, outlet control, and remote power-off
bindings are project-specific and are deliberately not installed by this
generic node.

## Synchronising Nodel node names

Copy the safe example inventory to the ignored production path:

```sh
cp inventory/nodel-node-names.example.tsv inventory/nodel-node-names.tsv
```

Edit `inventory/nodel-node-names.tsv` with the real device inventory. Each row
contains a balenaCloud fleet slug, physical MAC address, and desired Nodel node
name, separated by tabs. The production file is ignored because MAC addresses
and fleet details are site-specific; only the fictional example is committed.

The sync command validates every inventory row against detailed balenaCloud
device metadata and performs a read-only dry run by default:

```sh
python3 scripts/sync_node_names.py
```

Review the complete plan, then apply it:

```sh
python3 scripts/sync_node_names.py --apply
```

The default creates a device-wide `NODEL_NODE_NAME` variable. This works before
the first release containing Nodel is deployed, ensuring that the persistent
node is created with its final name. Device-variable changes restart the
device's services, so apply them during a suitable maintenance window.

For a device already running a `nodel` service, a service-specific variable can
be used instead:

```sh
python3 scripts/sync_node_names.py --service nodel
python3 scripts/sync_node_names.py --service nodel --apply
```

Keep using the same scope on later runs. The command only updates values that
differ, aborts before mutation if any MAC is missing or ambiguous, and can be
safely rerun after a partial network failure.

Clone consuming projects with their submodules:

```sh
git clone --recurse-submodules <project-url>
```

For an existing checkout, run:

```sh
git submodule update --init --recursive
```

## Local development

```sh
docker compose up --build
```

Browse to <http://localhost:8085>. The power actions intentionally fail outside
Balena because no Supervisor API is present. Screenshot requires a browser API
at the configured URL.

## Updating Nodel

Update both `NODEL_VERSION` and `NODEL_SHA256` in `Dockerfile`. The build fails
if the downloaded release does not match the expected SHA-256 checksum.
