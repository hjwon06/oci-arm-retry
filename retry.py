#!/usr/bin/env python3
"""OCI ARM Instance Auto-Retry for GitHub Actions — single attempt per run."""
import oci, os, sys, json, tempfile
from datetime import datetime

DISPLAY_NAME = "crawl-server"
SHAPE = "VM.Standard.A1.Flex"
OCPUS, MEMORY_GB, BOOT_VOLUME_GB = 1, 6, 100
IMAGE_OCID = "ocid1.image.oc1.ap-tokyo-1.aaaaaaaajrfukvwu6fypxmhyp2d5sgl74xhav7wnlxx3mzmk7lmfziqpgmla"
AD_NAME = "CTnO:AP-TOKYO-1-AD-1"
VCN_CIDR, SUBNET_CIDR = "10.0.0.0/16", "10.0.0.0/24"
SSH_PUB_KEY = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD4mXbL1Xe0e+6LFFcokFKzGfdGQzrM4em8QcvrdveU4/+j7vXfe7QZc6nDBSOK3KLFEgdGJKpebDwLaQER1n0PR1+/+uf1iugEtWxGrPCg3p3LijCGTWIg1KQDuZZJB3V/aHuauUhMmlcfj3zImQ10FBOev3vo7u501i633T0eeiGck6B+Ditu5rhCQZ0N6Piv5yxrdVUS6x4p/9UZaRTc/EQ/EiAXwF+gp/WgzoC+TujZAe2vFf9C1KmI0/PKLnwPy9uIXTM5mn/IvPgOHoKnw1VVs0ASb9mKP0UCAWWBFxH76Sekx8KGVlgTSn9VMZf8BAZFIQIMPJjPJEGYbUvb"


def log(msg):
    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] {msg}", flush=True)

def get_oci_config():
    """Build OCI config from environment variables."""
    key_content = os.environ.get("OCI_PRIVATE_KEY", "")
    if not key_content:
        log("ERROR: OCI_PRIVATE_KEY env not set")
        sys.exit(1)
    
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
    tmp.write(key_content)
    tmp.close()
    
    return {
        "user": "ocid1.user.oc1..aaaaaaaatlisxkejfpahgwmzlckurrhtgg3c2eom4e47faeipmuafschcmya",
        "fingerprint": "bb:86:91:3a:ba:52:12:62:51:f4:8d:63:ff:21:b1:2b",
        "tenancy": "ocid1.tenancy.oc1..aaaaaaaajqchyusbasdyid2jkwfucd66tj7feigy6u2cqutova5ctfnkotya",
        "region": "ap-tokyo-1",
        "key_file": tmp.name
    }


def find_or_create_vcn(vn_client, compartment_id):
    """Find existing VCN or create new one."""
    vcns = vn_client.list_vcns(compartment_id).data
    for v in vcns:
        if v.display_name == "crawl-vcn" and v.lifecycle_state == "AVAILABLE":
            log(f"Found VCN: {v.id}")
            return v.id
    
    vcn = vn_client.create_vcn(oci.core.models.CreateVcnDetails(
        compartment_id=compartment_id, cidr_block=VCN_CIDR, display_name="crawl-vcn"
    )).data
    vn_client.get_vcn(vcn.id)  # wait
    log(f"Created VCN: {vcn.id}")
    return vcn.id

def find_or_create_igw(vn_client, compartment_id, vcn_id):
    igws = vn_client.list_internet_gateways(compartment_id, vcn_id=vcn_id).data
    for g in igws:
        if g.lifecycle_state == "AVAILABLE":
            return g.id
    igw = vn_client.create_internet_gateway(oci.core.models.CreateInternetGatewayDetails(
        compartment_id=compartment_id, vcn_id=vcn_id, is_enabled=True, display_name="crawl-igw"
    )).data
    return igw.id


def setup_networking(vn_client, compartment_id):
    """Setup VCN, IGW, Route Table, Security List, Subnet."""
    vcn_id = find_or_create_vcn(vn_client, compartment_id)
    igw_id = find_or_create_igw(vn_client, compartment_id, vcn_id)
    
    # Route table
    rts = vn_client.list_route_tables(compartment_id, vcn_id=vcn_id).data
    rt_id = rts[0].id if rts else None
    if rt_id:
        vn_client.update_route_table(rt_id, oci.core.models.UpdateRouteTableDetails(
            route_rules=[oci.core.models.RouteRule(
                destination="0.0.0.0/0", destination_type="CIDR_BLOCK",
                network_entity_id=igw_id
            )]
        ))
    
    # Security list — allow SSH + HTTP + HTTPS
    sls = vn_client.list_security_lists(compartment_id, vcn_id=vcn_id).data
    sl_id = sls[0].id if sls else None
    if sl_id:
        ingress = [oci.core.models.IngressSecurityRule(
            protocol="6", source="0.0.0.0/0", source_type="CIDR_BLOCK",
            tcp_options=oci.core.models.TcpOptions(
                destination_port_range=oci.core.models.PortRange(min=p, max=p)
            )
        ) for p in [22, 80, 443]]
        vn_client.update_security_list(sl_id, oci.core.models.UpdateSecurityListDetails(
            ingress_security_rules=ingress,
            egress_security_rules=[oci.core.models.EgressSecurityRule(
                protocol="all", destination="0.0.0.0/0", destination_type="CIDR_BLOCK"
            )]
        ))

    # Subnet
    subnets = vn_client.list_subnets(compartment_id, vcn_id=vcn_id).data
    for s in subnets:
        if s.lifecycle_state == "AVAILABLE":
            log(f"Found Subnet: {s.id}")
            return s.id
    
    subnet = vn_client.create_subnet(oci.core.models.CreateSubnetDetails(
        compartment_id=compartment_id, vcn_id=vcn_id, cidr_block=SUBNET_CIDR,
        display_name="crawl-subnet", route_table_id=rt_id, security_list_ids=[sl_id]
    )).data
    log(f"Created Subnet: {subnet.id}")
    return subnet.id

def launch_instance(compute_client, compartment_id, subnet_id):
    """Single attempt to launch ARM instance."""
    try:
        details = oci.core.models.LaunchInstanceDetails(
            compartment_id=compartment_id,
            availability_domain=AD_NAME,
            display_name=DISPLAY_NAME,
            shape=SHAPE,
            shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=OCPUS, memory_in_gbs=MEMORY_GB
            ),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                image_id=IMAGE_OCID,
                boot_volume_size_in_gbs=BOOT_VOLUME_GB
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=subnet_id, assign_public_ip=True
            ),
            metadata={"ssh_authorized_keys": SSH_PUB_KEY}
        )
        instance = compute_client.launch_instance(details).data
        log(f"SUCCESS! Instance ID: {instance.id}")
        log(f"Display Name: {instance.display_name}")
        log(f"State: {instance.lifecycle_state}")
        return instance
    except oci.exceptions.ServiceError as e:
        if "capacity" in str(e.message).lower():
            log(f"Out of capacity — will retry next run")
            return None
        else:
            log(f"API Error: {e.status} — {e.message}")
            raise

def main():
    log("=== OCI ARM Retry (GitHub Actions) ===")
    config = get_oci_config()
    compartment_id = config["tenancy"]
    
    compute = oci.core.ComputeClient(config)
    vn = oci.core.VirtualNetworkClient(config)
    
    # Check if instance already exists
    instances = compute.list_instances(compartment_id).data
    for inst in instances:
        if inst.display_name == DISPLAY_NAME and inst.lifecycle_state in ("RUNNING", "PROVISIONING", "STARTING"):
            log(f"Instance already exists: {inst.id} ({inst.lifecycle_state})")
            print("::set-output name=instance_created::true")
            return
    
    subnet_id = setup_networking(vn, compartment_id)
    instance = launch_instance(compute, compartment_id, subnet_id)
    
    if instance:
        print("::set-output name=instance_created::true")
        # Get public IP
        try:
            vnic_attachments = compute.list_vnic_attachments(compartment_id, instance_id=instance.id).data
            if vnic_attachments:
                import time
                time.sleep(30)  # wait for VNIC
                vnic = vn.get_vnic(vnic_attachments[0].vnic_id).data
                log(f"Public IP: {vnic.public_ip}")
        except Exception as e:
            log(f"Could not get IP yet: {e}")
    else:
        print("::set-output name=instance_created::false")
        sys.exit(1)

if __name__ == "__main__":
    main()
