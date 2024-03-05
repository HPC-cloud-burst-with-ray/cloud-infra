import { Stack, CfnOutput } from 'aws-cdk-lib';
import { aws_iam as iam } from 'aws-cdk-lib';
import { aws_ec2 as ec2 } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { OnPremVpcResources } from './vpc';
import { EC2NodeResources } from './ec2';
import { EC2StackProps } from './utils';
import { RemovalPolicy } from 'aws-cdk-lib';
import * as efs from 'aws-cdk-lib/aws-efs';

export class OnPremStack extends Stack {
  constructor(scope: Construct, id: string, props: EC2StackProps) {
    super(scope, id, props);

    const { sshPubKey, cpuType, instanceSize, workerNodeNum } = props;
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

    const efsFileSystemPolicy = new iam.PolicyDocument({
      statements: [new iam.PolicyStatement({
        actions: ['*'],
        principals: [new iam.AnyPrincipal()],
        resources: ['*'],
        conditions: {
          Bool: {
            'elasticfilesystem:AccessedViaMountTarget': 'true',
          },
        },
      })],
    });


    const fileSystem = new efs.FileSystem(this, 'OnPremEfsFileSystem', {
      vpc: onpremVpc.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      securityGroup: onpremVpc.onPremSecurityGroup,
      encrypted: true,
      lifecyclePolicy: efs.LifecyclePolicy.AFTER_14_DAYS,
      performanceMode: efs.PerformanceMode.GENERAL_PURPOSE,
      throughputMode: efs.ThroughputMode.BURSTING,
      fileSystemPolicy: efsFileSystemPolicy,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    // create one login side ec2 instance
    const loginNode = new EC2NodeResources(this, 'OnPremLogin', {
      vpc: onpremVpc.vpc,
      securityGroup: onpremVpc.onPremSecurityGroup,
      sshPubKey: sshPubKey,
      cpuType: cpuType,
      instanceSize: instanceSize,
      nodeType: 'ONPREM_LOGIN',
      diskSize: 15,
    });

    // generate node id string with two digits
    const getNodeId = (id: number) => {
      if (id < 10) {
        return '0' + id;
      } else {
        return id;
      }
    };

    // create workerNodeNum worker nodes
    let workerNodesArray = [];
    for (let i = 0; i < workerNodeNum; i++) {
      const workerNode = new EC2NodeResources(this, 'OnPremWorker' + getNodeId(i), {
        vpc: onpremVpc.vpc,
        securityGroup: onpremVpc.onPremSecurityGroup,
        sshPubKey: sshPubKey,
        cpuType: cpuType,
        instanceSize: instanceSize,
        nodeType: 'ONPREM_WORKER',
        diskSize: 150,
      });
      workerNodesArray.push(workerNode);
    }

    // only add one worker node for now
    // const workerNode = new EC2NodeResources(this, 'OnPremWorker01', {
    //   vpc: onpremVpc.vpc,
    //   securityGroup: onpremVpc.onPremSecurityGroup,
    //   sshPubKey: sshPubKey,
    //   cpuType: cpuType,
    //   instanceSize: instanceSize,
    //   nodeType: 'ONPREM_WORKER',
    // });

    // allow login node to access worker node
    // fileSystem.connections.allowDefaultPortFrom(loginNode.instance);
    // fileSystem.connections.allowDefaultPortFrom(workerNode.instance);

    // give role to login node to do ssm:putParameter and s3 ops
    loginNode.instance.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ssm:PutParameter', 's3:*'],
      resources: ['*'],
    }));

    // give role to worker node to do ssm:putParameter and s3 ops
    for (let i = 0; i < workerNodeNum; i++) {
      workerNodesArray[i].instance.addToRolePolicy(new iam.PolicyStatement({
        actions: ['ssm:PutParameter', 's3:*'],
        resources: ['*'],
      }));
    }

    // mounting efs on login node
    // setup ssh key for login node
    loginNode.instance.userData.addCommands(
      "yum install -y amazon-efs-utils", 
      "yum install -y nfs-utils", 
      "file_system_id_1=" + fileSystem.fileSystemId, 
      "efs_mount_point_1=/home/ec2-user/share", 
      "mkdir -p ${efs_mount_point_1}",
      "if test -f \"/sbin/mount.efs\"; then " +
          "echo \"${file_system_id_1}:/ ${efs_mount_point_1} efs defaults,_netdev 0 0\" >> /etc/fstab; " +
      "else " +
          "echo \"${file_system_id_1}.efs." + Stack.of(this).region + ".amazonaws.com:/ ${efs_mount_point_1} nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport,_netdev 0 0\" >> /etc/fstab; " +
      "fi", 
      "ssh-keygen -t rsa -f /home/ec2-user/.ssh/id_rsa -q -P \"\"",
      "chown -R ec2-user:ec2-user /home/ec2-user/.ssh/",
      "aws ssm put-parameter --name \"/sshkey/onprem/loginNode/id_rsa_pub\" --type \"String\" --value \"$(cat /home/ec2-user/.ssh/id_rsa.pub)\" --overwrite",
      // Retry loop for the mount operation
      "max_attempts=5",
      "attempt=1",
      "mount_success=0",
      "while [ $attempt -le $max_attempts ]; do",
      "   mount -a -t efs,nfs4 defaults",
      "   if [ $? -eq 0 ]; then",
      "       echo \"Mount succeeded on attempt $attempt\"",
      "       mount_success=1",
      "       break",
      "   else",
      "       echo \"Mount attempt $attempt failed, retrying in 5 seconds...\"",
      "       attempt=$((attempt+1))",
      "       sleep 5",
      "   fi",
      "done",
      // Check if mount was successful
      "if [ $mount_success -ne 1 ]; then",
      "   echo \"Failed to mount EFS after $max_attempts attempts\"",
      "fi",
      "chown -R ec2-user:ec2-user ${efs_mount_point_1}",
      );

    // mounting efs on worker node
    // setup ssh key for worker node

    // single worker node case
    // workerNode.instance.userData.addCommands(
    //   "yum install -y amazon-efs-utils", 
    //   "yum install -y nfs-utils", 
    //   "file_system_id_1=" + fileSystem.fileSystemId, 
    //   "efs_mount_point_1=/home/ec2-user/share",
    //   "mkdir -p ${efs_mount_point_1}",
    //   "if test -f \"/sbin/mount.efs\"; then " +
    //       "echo \"${file_system_id_1}:/ ${efs_mount_point_1} efs defaults,_netdev 0 0\" >> /etc/fstab; " +
    //   "else " +
    //       "echo \"${file_system_id_1}.efs." + Stack.of(this).region + ".amazonaws.com:/ ${efs_mount_point_1} nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport,_netdev 0 0\" >> /etc/fstab; " +
    //   "fi", 
    //   "mount -a -t efs,nfs4 defaults",
    //   "mkdir -p /home/ec2-user/.ssh",
    //   "chown -R ec2-user:ec2-user /home/ec2-user/.ssh/",
    //   "chown -R ec2-user:ec2-user ${efs_mount_point_1}"
    // );

    for (let i = 0; i < workerNodeNum; i++) {
      workerNodesArray[i].instance.userData.addCommands(
        "yum install -y amazon-efs-utils", 
        "yum install -y nfs-utils", 
        "file_system_id_1=" + fileSystem.fileSystemId, 
        "efs_mount_point_1=/home/ec2-user/share",
        "mkdir -p ${efs_mount_point_1}",
        "if test -f \"/sbin/mount.efs\"; then " +
            "echo \"${file_system_id_1}:/ ${efs_mount_point_1} efs defaults,_netdev 0 0\" >> /etc/fstab; " +
        "else " +
            "echo \"${file_system_id_1}.efs." + Stack.of(this).region + ".amazonaws.com:/ ${efs_mount_point_1} nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport,_netdev 0 0\" >> /etc/fstab; " +
        "fi", 
        "mkdir -p /home/ec2-user/.ssh",
        "chown -R ec2-user:ec2-user /home/ec2-user/.ssh/",
        // Retry loop for the mount operation
        "max_attempts=5",
        "attempt=1",
        "mount_success=0",
        "while [ $attempt -le $max_attempts ]; do",
        "   mount -a -t efs,nfs4 defaults",
        "   if [ $? -eq 0 ]; then",
        "       echo \"Mount succeeded on attempt $attempt\"",
        "       mount_success=1",
        "       break",
        "   else",
        "       echo \"Mount attempt $attempt failed, retrying in 5 seconds...\"",
        "       attempt=$((attempt+1))",
        "       sleep 5",
        "   fi",
        "done",
        // Check if mount was successful
        "if [ $mount_success -ne 1 ]; then",
        "   echo \"Failed to mount EFS after $max_attempts attempts\"",
        "fi",
        "chown -R ec2-user:ec2-user ${efs_mount_point_1}",
      );
    }

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
