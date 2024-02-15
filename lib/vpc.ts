import { Construct } from 'constructs';
import {
    SecurityGroup,
    Peer,
    Port,
    SubnetType,
    Vpc,
  } from 'aws-cdk-lib/aws-ec2';

export class OnPremVpcResources extends Construct {
    public onPremSecurityGroup: SecurityGroup;
    public vpc: Vpc;
  
    constructor(scope: Construct, id: string) {
        super(scope, id);
  
        // Create a VPC with public subnets in 1 AZ
        // login node in this vpc will have public ip
        // worker nodes in this vpc will not have public ip (NAT)
        this.vpc = new Vpc(this, 'OnPremVPC', {
            cidr: '10.0.0.0/16',
            natGateways: 1,
            subnetConfiguration: [
            {
                cidrMask: 24,
                name: 'ServerPublic',
                subnetType: SubnetType.PUBLIC,
                mapPublicIpOnLaunch: true,
            },
            {
                cidrMask: 24,
                name: 'ServerPrivate',
                subnetType: SubnetType.PRIVATE_WITH_EGRESS,
            }
            ],
            maxAzs: 1,
        });

  
        // Create a security group for SSH
        this.onPremSecurityGroup = new SecurityGroup(this, 'OnPremSecurityGroup', {
            vpc: this.vpc,
            description: 'Security Group for SSH/HTTP/HTTPS/Ray',
            allowAllOutbound: true,
        });
  
        // Allow SSH inbound traffic on TCP port 22
        this.onPremSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(22));
        // allow HTTPS HTTP and certain ports for ray
        this.onPremSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(443));
        this.onPremSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(80));
        this.onPremSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcpRange(10000, 65535));
        // gcs port 6379
        this.onPremSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(6379));
        // add dashboard port 8265
        this.onPremSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(8265));
        // also allow port 2049 for efs
        this.onPremSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(2049));
        this.onPremSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(8888));
        // add ping with ICMP
        this.onPremSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.icmpPing());
        // add UDP for iperf3 on ports from 10000 to 65535
        this.onPremSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.udpRange(10000, 65535));
    }
}

export class CloudVpcResources extends Construct {
    public cloudSecurityGroup: SecurityGroup;
    public vpc: Vpc;
  
    constructor(scope: Construct, id: string) {
        super(scope, id);
  
        // Create a VPC with public subnets in 1 AZ
        this.vpc = new Vpc(this, 'CloudVPC', {
            cidr: '11.0.0.0/16',
            natGateways: 0,
            subnetConfiguration: [
            {
                cidrMask: 24,
                name: 'ServerPublic',
                subnetType: SubnetType.PUBLIC,
                mapPublicIpOnLaunch: true,
            },
            ],
            maxAzs: 1,
        });
  
        // Create a security group for SSH
        this.cloudSecurityGroup = new SecurityGroup(this, 'CloudSecurityGroup', {
            vpc: this.vpc,
            description: 'Security Group for SSH/HTTP/HTTPS/Ray',
            allowAllOutbound: true,
        });
  
        // Allow SSH inbound traffic on TCP port 22
        this.cloudSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(22));
        // allow HTTPS HTTP and certain ports for ray
        this.cloudSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(443));
        this.cloudSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(80));
        this.cloudSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcpRange(10000, 65535));
        // gcs port 6379
        this.cloudSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(6379));
        // add dashboard port 8265
        this.cloudSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(8265));
        // also allow port 2049 for efs
        this.cloudSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(2049));
        // add 8888 for jupyter and file transfer
        this.cloudSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(8888));
        // add support for ping (ICMP)
        this.cloudSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.icmpPing());
        // add UDP for iperf3 on ports from 10000 to 65535
        this.cloudSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.udpRange(10000, 65535));
    }
}

export class DevVpcResources extends Construct {
    public devSecurityGroup: SecurityGroup;
    public vpc: Vpc;
  
    constructor(scope: Construct, id: string) {
        super(scope, id);
  
        // Create a VPC with public subnets in 1 AZ
        this.vpc = new Vpc(this, 'DevVPC', {
            natGateways: 0,
            subnetConfiguration: [
            {
                cidrMask: 24,
                name: 'ServerPublic',
                subnetType: SubnetType.PUBLIC,
                mapPublicIpOnLaunch: true,
            },
            ],
            maxAzs: 1,
        });
  
        // Create a security group for SSH
        this.devSecurityGroup = new SecurityGroup(this, 'DevSecurityGroup', {
            vpc: this.vpc,
            description: 'Security Group for SSH/HTTP/HTTPS/NFS',
            allowAllOutbound: true,
        });

        this.devSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(22));
        this.devSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(443));
        this.devSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(80));
        this.devSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(2049));
        this.devSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(8888));
        // add support for ping
        this.devSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.icmpPing());
        // add support for iperf3 udp and tcp
        this.devSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.udpRange(10000, 65535));
        this.devSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcpRange(10000, 65535));
    }
}