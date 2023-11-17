import { Stack, StackProps, CfnOutput } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { OnPremVpcResources } from './vpc';
import { EC2NodeResources } from './ec2';
import { EC2StackProps } from './utils';
import * as efs from 'aws-cdk-lib/aws-efs';

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

    const fileSystem = new efs.FileSystem(this, 'OnPremEfsFileSystem', {
      vpc: onpremVpc.vpc,
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

    // mounting efs on login node
    loginNode.instance.userData.addCommands(
      "yum install -y amazon-efs-utils", 
      "yum install -y nfs-utils", 
      "file_system_id_1=" + fileSystem.fileSystemId, 
      "efs_mount_point_1=/home", 
      "mkdir -p ${efs_mount_point_1}",
      "if test -f \"/sbin/mount.efs\"; then " +
          "echo \"${file_system_id_1}:/ ${efs_mount_point_1} efs defaults,_netdev 0 0\" >> /etc/fstab; " +
      "else " +
          "echo \"${file_system_id_1}.efs." + Stack.of(this).region + ".amazonaws.com:/ ${efs_mount_point_1} nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport,_netdev 0 0\" >> /etc/fstab; " +
      "fi", 
      "mount -a -t efs,nfs4 defaults"
    );

    // mounting efs on worker node
    workerNode.instance.userData.addCommands(
      "yum install -y amazon-efs-utils", 
      "yum install -y nfs-utils", 
      "file_system_id_1=" + fileSystem.fileSystemId, 
      "efs_mount_point_1=/home", 
      "mkdir -p ${efs_mount_point_1}",
      "if test -f \"/sbin/mount.efs\"; then " +
          "echo \"${file_system_id_1}:/ ${efs_mount_point_1} efs defaults,_netdev 0 0\" >> /etc/fstab; " +
      "else " +
          "echo \"${file_system_id_1}.efs." + Stack.of(this).region + ".amazonaws.com:/ ${efs_mount_point_1} nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport,_netdev 0 0\" >> /etc/fstab; " +
      "fi", 
      "mount -a -t efs,nfs4 defaults"
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
