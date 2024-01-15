import { Stack, CfnOutput } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { CloudVpcResources } from './vpc';
import { EC2NodeResources } from './ec2';
import { EC2StackProps } from './utils';
import { aws_iam as iam } from 'aws-cdk-lib';
import { aws_ec2 as ec2 } from 'aws-cdk-lib';
import * as efs from 'aws-cdk-lib/aws-efs';

export class CloudStack extends Stack {
  constructor(scope: Construct, id: string, props: EC2StackProps) {
    super(scope, id, props);

    const { sshPubKey, cpuType, instanceSize, workerNodeNum } = props;
    // assert cpuType is x86_64
    if (cpuType !== 'x86_64') {
      throw new Error('cpuType must be x86_64');
    }

    // create cloud side vpc
    const cloudVpc = new CloudVpcResources(this, 'CloudVPC');

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

    const fileSystem = new efs.FileSystem(this, 'CloudEfsFileSystem', {
      vpc: cloudVpc.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      securityGroup: cloudVpc.cloudSecurityGroup,
      encrypted: true,
      lifecyclePolicy: efs.LifecyclePolicy.AFTER_14_DAYS,
      performanceMode: efs.PerformanceMode.GENERAL_PURPOSE,
      throughputMode: efs.ThroughputMode.BURSTING,
      fileSystemPolicy: efsFileSystemPolicy,
    });

    // generate node id string with two digits
    const getNodeId = (id: number) => {
      if (id < 10) {
        return '0' + id;
      } else {
        return id;
      }
    };

    let cloudNodesArray = [];
    for (let i = 0; i < workerNodeNum; i++) {
      cloudNodesArray.push(new EC2NodeResources(this, 'CloudNode'+getNodeId(i), {
        vpc: cloudVpc.vpc,
        securityGroup: cloudVpc.cloudSecurityGroup,
        sshPubKey: sshPubKey,
        cpuType: cpuType,
        instanceSize: instanceSize,
        nodeType: 'CLOUD',
      }));
    }

    // create one cloud side ec2 instance (might be many nodes in the future)
    // const cloudNode = new EC2NodeResources(this, 'CloudNode01', {
    //   vpc: cloudVpc.vpc,
    //   securityGroup: cloudVpc.cloudSecurityGroup,
    //   sshPubKey: sshPubKey,
    //   cpuType: cpuType,
    //   instanceSize: instanceSize,
    //   nodeType: 'CLOUD',
    // });

    // add user data commands to the cloud node instance
    // cloudNode.instance.userData.addCommands(
    //   "ssh-keygen -t rsa -f /home/ec2-user/.ssh/id_rsa -q -N ''",
    //   "aws ssm put-parameter --name \"/sshkey/cloud/cloudNode01/id_rsa_pub\" --type \"String\" --value \"$(cat /home/ec2-user/.ssh/id_rsa.pub)\" --overwrite"
    // );

    // add user data commands to all the cloud node instance
    for (let i = 0; i < workerNodeNum; i++) {
      cloudNodesArray[i].instance.userData.addCommands(
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
        "ssh-keygen -t rsa -f /home/ec2-user/.ssh/id_rsa -q -N ''",
        "chown -R ec2-user:ec2-user /home/ec2-user/.ssh/",
        "aws ssm put-parameter --name \"/sshkey/cloud/cloudNode"+ getNodeId(i) +"/id_rsa_pub\" --type \"String\" --value \"$(cat /home/ec2-user/.ssh/id_rsa.pub)\" --overwrite",
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

    // add putPrarams to the cloud node instance iam policy
    // cloudNode.instance.addToRolePolicy(new iam.PolicyStatement({
    //   actions: ['ssm:PutParameter'],
    //   resources: ['*'],
    // }));

    // add putPrarams to all the cloud node instance iam policy
    for (let i = 0; i < workerNodeNum; i++) {
      cloudNodesArray[i].instance.addToRolePolicy(new iam.PolicyStatement({
        actions: ['ssm:PutParameter'],
        resources: ['*'],
      }));
    }

    // cfn output to all the cloud node instance id
    for (let i = 0; i < workerNodeNum; i++) {
      const cloudNode = cloudNodesArray[i];
      // SSM Command to start a session
      new CfnOutput(this, 'ssmCommand'+getNodeId(i), {
        value: `aws ssm start-session --target ${cloudNode.instance.instanceId}`,
      });

      // SSH Command to connect to the EC2 Instance
      new CfnOutput(this, 'sshCommand'+getNodeId(i), {
        value: `ssh ec2-user@${cloudNode.instance.instancePublicDnsName}`,
      });
    }
  }
}
