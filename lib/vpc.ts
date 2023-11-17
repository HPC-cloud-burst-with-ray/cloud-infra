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
        // allow port range 30000 ~ 31000 for ray and also 6379
        this.onPremSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcpRange(30000, 31000));
        this.onPremSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(6379));
    }
}

export class CloudVpcResources extends Construct {
    public cloudSecurityGroup: SecurityGroup;
    public vpc: Vpc;
  
    constructor(scope: Construct, id: string) {
        super(scope, id);
  
        // Create a VPC with public subnets in 1 AZ
        this.vpc = new Vpc(this, 'CloudVPC', {
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
        // allow port range 30000 ~ 31000 for ray and also 6379
        this.cloudSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcpRange(30000, 31000));
        this.cloudSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(6379));
    }
}