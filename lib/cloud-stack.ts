import { Stack, CfnOutput } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { CloudVpcResources } from './vpc';
import { EC2NodeResources } from './ec2';
import { EC2StackProps } from './utils';
import { aws_iam as iam } from 'aws-cdk-lib';

export class CloudStack extends Stack {
  constructor(scope: Construct, id: string, props: EC2StackProps) {
    super(scope, id, props);

    const { sshPubKey, cpuType, instanceSize } = props;
    // assert cpuType is x86_64
    if (cpuType !== 'x86_64') {
      throw new Error('cpuType must be x86_64');
    }

    // create cloud side vpc
    const cloudVpc = new CloudVpcResources(this, 'CloudVPC');

    // create one cloud side ec2 instance (might be many nodes in the future)
    const cloudNode = new EC2NodeResources(this, 'CloudNode01', {
      vpc: cloudVpc.vpc,
      securityGroup: cloudVpc.cloudSecurityGroup,
      sshPubKey: sshPubKey,
      cpuType: cpuType,
      instanceSize: instanceSize,
      nodeType: 'CLOUD',
    });

    // add user data commands to the cloud node instance
    cloudNode.instance.userData.addCommands(
      "ssh-keygen -t rsa -f /home/ec2-user/.ssh/id_rsa -q -N ''",
      "aws ssm put-parameter --name \"/sshkey/cloud/cloudNode01/id_rsa_pub\" --type \"String\" --value \"$(cat /home/ec2-user/.ssh/id_rsa.pub)\" --overwrite"
    );

    // add putPrarams to the cloud node instance iam policy
    cloudNode.instance.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ssm:PutParameter'],
      resources: ['*'],
    }));


    // SSM Command to start a session
    new CfnOutput(this, 'ssmCommand', {
      value: `aws ssm start-session --target ${cloudNode.instance.instanceId}`,
    });

    // SSH Command to connect to the EC2 Instance
    new CfnOutput(this, 'sshCommand', {
      value: `ssh ec2-user@${cloudNode.instance.instancePublicDnsName}`,
    });

  }
}
