import { Stack, CfnOutput } from 'aws-cdk-lib';
import { aws_iam as iam } from 'aws-cdk-lib';
import { aws_ec2 as ec2 } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { OnPremVpcResources } from './vpc';
import { EC2NodeResources } from './ec2';
import { EC2StackProps } from './utils';
import * as efs from 'aws-cdk-lib/aws-efs';
import { on } from 'events';

export class OnPremStack extends Stack {
  constructor(scope: Construct, id: string, props: EC2StackProps) {
    super(scope, id, props);

    const { sshPubKey, cpuType, instanceSize } = props;
    // assert cpuType is x86_64
    if (cpuType !== 'x86_64') {
      throw new Error('cpuType must be x86_64');
    }

    // create onprem side vpc
    const onpremVpc = new OnPremVpcResources(this, 'OnPremVPC');

    const cfnInstanceConnectEndpoint = new ec2.CfnInstanceConnectEndpoint(this, 'OnPremVpcInstanceEndpoint', {
      subnetId: onpremVpc.vpc.privateSubnets[0].subnetId,
      securityGroupIds: [onpremVpc.onPremSecurityGroup.securityGroupId]
    });

    // print out env for account id and region
    // console.log('account id: ' + Stack.of(this).account);
    // console.log('region: ' + Stack.of(this).region);


    const fileSystem = new efs.FileSystem(this, 'OnPremEfsFileSystem', {
      vpc: onpremVpc.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroup: onpremVpc.onPremSecurityGroup,
      encrypted: true,
      lifecyclePolicy: efs.LifecyclePolicy.AFTER_14_DAYS,
      performanceMode: efs.PerformanceMode.GENERAL_PURPOSE,
      throughputMode: efs.ThroughputMode.BURSTING
    });


    // create one login side ec2 instance
    const loginNode = new EC2NodeResources(this, 'OnPremLogin', {
      vpc: onpremVpc.vpc,
      securityGroup: onpremVpc.onPremSecurityGroup,
      sshPubKey: sshPubKey,
      cpuType: cpuType,
      instanceSize: instanceSize,
      nodeType: 'ONPREM_LOGIN',
    });

    // only add one worker node for now
    const workerNode = new EC2NodeResources(this, 'OnPremWorker01', {
      vpc: onpremVpc.vpc,
      securityGroup: onpremVpc.onPremSecurityGroup,
      sshPubKey: sshPubKey,
      cpuType: cpuType,
      instanceSize: instanceSize,
      nodeType: 'ONPREM_WORKER',
    });

    // allow login node to access worker node
    fileSystem.connections.allowDefaultPortFrom(loginNode.instance);
    fileSystem.connections.allowDefaultPortFrom(workerNode.instance);

    // give role to login node to do ssm:putParameter
    loginNode.instance.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ssm:PutParameter'],
      resources: ['*'],
    }));

    // mounting efs on login node
    // setup ssh key for login node
    loginNode.instance.userData.addCommands(
      "yum install -y amazon-efs-utils", 
      "yum install -y nfs-utils", 
      "file_system_id_1=" + fileSystem.fileSystemId, 
      "efs_mount_point_1=/home/ec2-user", 
      "mkdir -p ${efs_mount_point_1}",
      "if test -f \"/sbin/mount.efs\"; then " +
          "echo \"${file_system_id_1}:/ ${efs_mount_point_1} efs defaults,_netdev 0 0\" >> /etc/fstab; " +
      "else " +
          "echo \"${file_system_id_1}.efs." + Stack.of(this).region + ".amazonaws.com:/ ${efs_mount_point_1} nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport,_netdev 0 0\" >> /etc/fstab; " +
      "fi", 
      "mount -a -t efs,nfs4 defaults",
      "chown ec2-user:ec2-user /home/ec2-user",
      "chmod 777 /home/ec2-user",
      "ssh-keygen -t rsa -f /home/ec2-user/.ssh/id_rsa -q -P \"\"",
      "aws ssm put-parameter --name \"/sshkey/onprem/loginNode/id_rsa_pub\" --type \"String\" --value \"$(cat /home/ec2-user/.ssh/id_rsa.pub)\" --overwrite"
    );

    // mounting efs on worker node
    // setup ssh key for worker node
    workerNode.instance.userData.addCommands(
      "yum install -y amazon-efs-utils", 
      "yum install -y nfs-utils", 
      "file_system_id_1=" + fileSystem.fileSystemId, 
      "efs_mount_point_1=/home/ec2-user",
      "mkdir -p ${efs_mount_point_1}",
      "if test -f \"/sbin/mount.efs\"; then " +
          "echo \"${file_system_id_1}:/ ${efs_mount_point_1} efs defaults,_netdev 0 0\" >> /etc/fstab; " +
      "else " +
          "echo \"${file_system_id_1}.efs." + Stack.of(this).region + ".amazonaws.com:/ ${efs_mount_point_1} nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport,_netdev 0 0\" >> /etc/fstab; " +
      "fi", 
      "mount -a -t efs,nfs4 defaults",
      "chown ec2-user:ec2-user /home/ec2-user",
      "chmod 777 /home/ec2-user",
      "mkdir -p /home/ec2-user/.ssh"
    );

    // SSM Command to start a session
    new CfnOutput(this, 'ssmCommand', {
      value: `aws ssm start-session --target ${loginNode.instance.instanceId}`,
    });

    // SSH Command to connect to the EC2 Instance
    new CfnOutput(this, 'sshCommand', {
      value: `ssh ec2-user@${loginNode.instance.instancePublicDnsName}`,
    });

  }
}
