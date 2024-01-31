import { RemovalPolicy, Duration, Stack } from 'aws-cdk-lib';
import {
    Vpc,
    SecurityGroup,
    Instance,
    InstanceType,
    InstanceClass,
    InstanceSize,
    CloudFormationInit,
    InitConfig,
    InitFile,
    InitCommand,
    UserData,
    MachineImage,
    AmazonLinuxCpuType,
    SubnetSelection,
    SubnetType,
} from 'aws-cdk-lib/aws-ec2';
import {
    Role,
    ServicePrincipal,
    ManagedPolicy,
    PolicyDocument,
    PolicyStatement,
} from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

// node types
// CLOUD: cloud node
// ONPREM_LOGIN: on-prem login node
// ONPREM_WORKER: on-prem worker node

interface ServerProps {
    vpc: Vpc;
    securityGroup: SecurityGroup;
    sshPubKey: string;
    cpuType: string;    // must be x86_64 for now
    instanceSize: string;
    nodeType: string;
    diskSize: number;
}

let cpuType: AmazonLinuxCpuType;
let instanceClass: InstanceClass;
let instanceSize: InstanceSize;
let subnetSelection: SubnetSelection = {};
let associatePublicIpAddress: boolean = false;
let diskSize: number = 15;

export class EC2NodeResources extends Construct{
    public instance: Instance;

    constructor(scope: Construct, id: string, props: ServerProps) {
        super(scope, id);

        // log server props for debug 
        // console.log(props);

        const serverRole = new Role(this, 'serverEc2Role', {
            assumedBy: new ServicePrincipal('ec2.amazonaws.com'),
            inlinePolicies: {
              ['RetentionPolicy']: new PolicyDocument({
                statements: [
                  new PolicyStatement({
                    resources: ['*'],
                    actions: ['logs:PutRetentionPolicy'],
                  }),
                ],
              }),
            },
            managedPolicies: [
              ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMManagedInstanceCore'),
              ManagedPolicy.fromAwsManagedPolicyName('CloudWatchAgentServerPolicy'),
            ],
        });

        const userData = UserData.forLinux();

        // Add user data that is used to configure the EC2 instance
        userData.addCommands(
            'yum update -y',
            'yum install -y amazon-cloudwatch-agent nodejs python3-pip iptables nftables zip unzip git vim tmux python3-devel',
            'ln -s /usr/bin/python3 /usr/bin/python',
            'yum install -y java-1.8.0-amazon-corretto-devel'
        );
    
        // determine cpu and instance size
        if (props.cpuType === 'x86_64') {
            cpuType = AmazonLinuxCpuType.X86_64;
            instanceClass = InstanceClass.M5;
        } else {
            // don't support arm yet, raise error
            throw new Error('Unsupported cpu type');
        }
        
        switch (props.instanceSize) {
            case 'LARGE':
              instanceSize = InstanceSize.LARGE;
              break;
            case 'XLARGE':
              instanceSize = InstanceSize.XLARGE;
              break;
            case 'XLARGE2':
              instanceSize = InstanceSize.XLARGE2;
              break;
            case 'XLARGE4':
              instanceSize = InstanceSize.XLARGE4;
              break;
            default:
              instanceSize = InstanceSize.LARGE;
        }

        // determine subnet
        if (props.nodeType === 'CLOUD') {
            subnetSelection = { subnetType: SubnetType.PUBLIC,};
            associatePublicIpAddress = true;
        }else if (props.nodeType === 'ONPREM_LOGIN') {
            subnetSelection = { subnetType: SubnetType.PUBLIC,};
            associatePublicIpAddress = true;
        }else if (props.nodeType === 'ONPREM_WORKER') {
            subnetSelection = { subnetType: SubnetType.PRIVATE_WITH_EGRESS,};
            associatePublicIpAddress = false;
        }else {
            throw new Error('Unsupported node type');
        }

        // log ssh key for debug
        // console.log("ssh key: " + props.sshPubKey);

        // calc disk size
        diskSize = Math.max(diskSize, props.diskSize);

        // create instance
        this.instance = new Instance(this, 'Instance', {
            vpc: props.vpc,
            vpcSubnets: subnetSelection,
            associatePublicIpAddress: associatePublicIpAddress,
            securityGroup: props.securityGroup,
            instanceType: InstanceType.of(instanceClass, instanceSize),
            // gives more disk space
            blockDevices: [
                {
                    deviceName: '/dev/xvda',
                    volume: {
                        ebsDevice: {
                            volumeSize: diskSize,
                        },
                    },
                },
            ],
            machineImage: MachineImage.latestAmazonLinux2023({
            cachedInContext: false,
            cpuType: cpuType,
            }),
            userData: userData,
            init: CloudFormationInit.fromConfigSets({
                configSets: {
                    default: ['config'],
                },
                configs: {
                    config: new InitConfig([
                    InitFile.fromObject('/etc/config.json', {
                        // Use CloudformationInit to create an object on the EC2 instance
                        STACK_ID: Stack.of(this).artifactId,
                    }),
                    InitFile.fromFileInline(
                        // Use CloudformationInit to copy a file to the EC2 instance
                        '/tmp/amazon-cloudwatch-agent.json',
                        'lib/resources/server/config/amazon-cloudwatch-agent.json',
                    ),
                    InitFile.fromFileInline(
                        '/etc/config.sh',
                        'lib/resources/server/config/config.sh',
                    ),
                    InitFile.fromString(
                        // Use CloudformationInit to write a string to the EC2 instance
                        '/home/ec2-user/.ssh/authorized_keys',
                        props.sshPubKey + '\n',
                    ),
                    InitCommand.shellCommand('chmod +x /etc/config.sh'), // Use CloudformationInit to run a shell command on the EC2 instance
                    InitCommand.shellCommand('/etc/config.sh'),
                    ]),
                },
            }),
    
            initOptions: {
            timeout: Duration.minutes(10),
            includeUrl: true,
            includeRole: true,
            printLog: true,
            },
            role: serverRole,
        });

        // this.instance.addSecurityGroup(props.securityGroup);
    }
}
