import netaddr, pynetbox, re
from braceexpand import braceexpand
from pprint import pprint

# set netbox-docker api address and token
nb = pynetbox.api(
    'http://192.168.137.100:8000',
    token='0123456789abcdef0123456789abcdef01234567'
)

# get tenancy, create new if necessary
upstart_crow = nb.tenancy.tenants.get(name='upstart_crow')
if not upstart_crow:
    upstart_crow = nb.tenancy.tenants.create(
        name = 'upstart_crow',
        slug = 'upstart_crow')


# get regions
all_regions = nb.dcim.regions.all()
def create_region(region):
    slug = region.lower()
    if region not in [x.name for x in all_regions]:
        region = nb.dcim.regions.create(
            name = region,
            slug = slug
            )

# get emea region
create_region('EMEA')
emea = nb.dcim.regions.get(name='EMEA')

# check if site LD4 exists
ld4 = nb.dcim.sites.get(name='LD4')
if not ld4:
    ld4 = nb.dcim.sites.create(
        name = 'LD4',
        region = emea.id,
        slug = 'ld4')

# get active device roles
roles = nb.dcim.device_roles.all()

# create roles
spine = nb.dcim.device_roles.get(name='spine')
leaf = nb.dcim.device_roles.get(name='leaf')
if 'spine' not in [x.name for x in roles]:
    spine = nb.dcim.device_roles.create(
        name = 'spine',
        slug = 'spine')
if 'leaf' not in [x.name for x in roles]:
    leaf = nb.dcim.device_roles.create(
        name = 'leaf',
        slug = 'leaf')

# get active RIR's
all_rirs = nb.ipam.rirs.all()

# create rfc1918 RIR
if 'rfc1918' not in [x.name for x in all_rirs]:
    rfc1918 = nb.ipam.rirs.create(
        name = 'rfc1918',
        is_private = True,
        slug = 'rfc1918')

# get active ipam roles
ipam_roles = nb.ipam.roles.all()

# define function for ipam role creation
def create_ipam_role(role_name):
    if role_name not in [x.name for x in ipam_roles]:
        role_name = nb.ipam.roles.create(
            name = role_name,
            slug = role_name,
            description = role_name)

# create ipam roles for subnet
create_ipam_role('loopback')
create_ipam_role('oob_mgmt')
create_ipam_role('interswitch_link')

# get active aggregates
all_aggregates = nb.ipam.aggregates.all()

def create_ip_aggregate(prefix):
    if str(prefix) not in [x.prefix for x in all_aggregates]:
        role = nb.ipam.aggregates.create(
            prefix = str(prefix),
            site = ld4.id,
            rir = rfc1918.id,
            tenant = upstart_crow.id)

# get active prefixes
all_prefixes = nb.ipam.prefixes.all()

# define function for prefix creation
def create_ip_prefix(prefix, role, pool):
    # get role.id
    role = nb.ipam.roles.get(name=role)
    if str(prefix) not in [x.prefix for x in all_prefixes]:
        role = nb.ipam.prefixes.create(
            prefix = str(prefix),
            role = role.id,
            site = ld4.id,
            tenant = upstart_crow.id,
            is_pool = pool)

# define aggregate networks
loopback_agg = netaddr.IPNetwork('150.0.0.0/8')
interswitch_link_agg = netaddr.IPNetwork('155.0.0.0/8')
oob_mgmt_agg = netaddr.IPNetwork('192.168.0.0/16')

# create ip aggregates
create_ip_aggregate(loopback_agg)
create_ip_aggregate(interswitch_link_agg)
create_ip_aggregate(oob_mgmt_agg)

# create loopback prefixes
x = 1
while x < 7:
    loopback = netaddr.IPNetwork(f"150.{x}.{x}.0/24")
    create_ip_prefix(loopback, 'loopback', True)
    x += 1

# create interswitch links for spine1
x = 11
while x < 16:
    interswitch_link = netaddr.IPNetwork(f"155.1.{x}.0/24")
    create_ip_prefix(interswitch_link, 'interswitch_link', False)
    x += 1

# create interswitch links for spine2
x = 21
while x < 26:
    interswitch_link = netaddr.IPNetwork(f"155.1.{x}.0/24")
    create_ip_prefix(interswitch_link, 'interswitch_link', False)
    x += 1

# create oob prefix
oob_mgmt = netaddr.IPNetwork('192.168.137.0/24')
create_ip_prefix(oob_mgmt, 'oob_mgmt', False)

# add 'cisco' as a new manufacturer
cisco = nb.dcim.manufacturers.get(name='cisco')
if not cisco:
    cisco = nb.dcim.manufacturers.create(
        name = 'cisco',
        slug = 'cisco')

# add 'ios' as a new platform
ios = nb.dcim.platforms.get(name='ios')
if not ios:
    ios = nb.dcim.platforms.create(
        name = 'ios',
        slug = 'ios')

# add the iosv device type
iosv = nb.dcim.device_types.get(model='iosv')
if not iosv:
    iosv = nb.dcim.device_types.create(
        model = 'iosv',
        manufacturer = ios.id,
        slug = 'iosv')

# create ios interface template
ios_interfaces = ['GigabitEthernet0/{0..5}']

# create an empty set
asserted_ios_interface_list = set()

# build set of ios interfaces
for port in ios_interfaces:
    asserted_ios_interface_list.update(braceexpand(port))

# convert set to dict and set port speed
interface_data = {}
for port in asserted_ios_interface_list:
    data = {}
    intf_type = '1000base-t'
    mgmt_status = False
    # set gig0/0 as oob_mgmt port
    if port == 'GigabitEthernet0/0':
        mgmt_status = True
    data.setdefault(port, dict(device_type=iosv.id, name=port,
                               mgmt_only=mgmt_status, type=intf_type))
    interface_data.update(data)

# add interface template for ios to netbox:
for intf, intf_data in interface_data.items():
    try:
        # check if interfaces already exist
        ifGet = nb.dcim.interface_templates.get(devicetype_id=intf_data['device_type'], 
                                                name=intf)
        if ifGet:
            continue
        else:
            # create interfaces if they don't exist
            ifSuccess = nb.dcim.interface_templates.create(
                device_type = intf_data['device_type'],
                name = intf,
                type = intf_data['type'],
                mgmt_only = intf_data['mgmt_only'],
                )
    except pynetbox.RequestError as e:
        print(e.error)    

# create node list:
nodes = ['spine1', 'spine2', 'leaf1', 'leaf2', 'leaf3', 'leaf4', 'leaf5']

# create an empty dict to store all device data
master = {}

# build out master dict for each node
for node in nodes:
    device_type = iosv.id
    device_role = leaf.id
    # set spine device_role
    if node.startswith('spine'):
        device_role = spine.id
    tenant = upstart_crow.id
    platform = ios.id
    site = ld4.id
    status = 'active'
    # set primary_ip4
    x = node[-1]
    primary_ip4 = {'address': f'150.1.{x}.{x}/32'}
    interfaces = {}
    for intf, intf_data in interface_data.items():
        # create empty dict per interface
        data = {}
        # set default parameters
        name = intf
        device = None
        description = None
        type = intf_data['type']
        ip = None
        mode = None
        enabled = False
        lag = None
        tagged_vlans = None
        untagged_vlan = None
        data.setdefault(intf.title(), dict(description=description,
                                           lag=lag, mode=mode, 
                                           tagged_vlans=tagged_vlans,
                                           untagged_vlan=untagged_vlan,
                                           type='virtual', ip=ip,
                                           enabled=enabled))
        interfaces.update(data)
    master.setdefault(node, dict(name=node, device_type=device_type,
                                 device_role=device_role, tenant=tenant,
                                 platform=platform, site=site, status=status,
                                 primary_ip4=primary_ip4,
                                 interfaces=interfaces))

pprint(master)
