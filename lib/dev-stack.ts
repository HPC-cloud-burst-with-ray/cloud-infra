import { Stack, CfnOutput } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { DevVpcResources } from './vpc';
import { EC2NodeResources } from './ec2';
import { EC2StackProps } from './utils';
import { assert } from 'console';
import { aws_iam as iam } from 'aws-cdk-lib';

export class DevStack extends Stack {
  constructor(scope: Construct, id: string, props: EC2StackProps) {
    super(scope, id, props);

    const { sshPubKey, cpuType, instanceSize, workerNodeNum } = props;

    assert(workerNodeNum === 1, 'workerNodeNum for dev stack must be 1 (only one compile machine is needed)');

    // assert cpuType is x86_64
    if (cpuType !== 'x86_64') {
      throw new Error('cpuType must be x86_64');
    }

    // get default vpc
    const devVpc = new DevVpcResources(this, 'DevVPC');

    const devNode = new EC2NodeResources(this, "DevNodeForCompile", {
        vpc: devVpc.vpc,
        securityGroup: devVpc.devSecurityGroup,
        sshPubKey: sshPubKey,
        cpuType: cpuType,
        instanceSize: instanceSize,
        nodeType: 'CLOUD',
        diskSize: 50,
    });

    devNode.instance.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ssm:PutParameter', 's3:*'],
      resources: ['*'],
    }));

    devNode.instance.userData.addCommands(
        "yum groupinstall -y 'Development Tools' ",
        "yum install -y psmisc",
        "chown -R ec2-user:ec2-user /home/ec2-user/.ssh/"
    );

    // SSM Command to start a session
    new CfnOutput(this, 'ssmCommand', {
    value: `aws ssm start-session --target ${devNode.instance.instanceId}`,
    });

    // SSH Command to connect to the EC2 Instance
    new CfnOutput(this, 'sshCommand', {
    value: `ssh ec2-user@${devNode.instance.instancePublicDnsName}`,
    });
  }
}
