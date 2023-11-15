# Welcome to your CDK TypeScript project

This is a blank project for CDK development with TypeScript.

The `cdk.json` file tells the CDK Toolkit how to execute your app.

## setup environment for CDK

*docs about CDK and aws cli*
```
https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html
https://aws.amazon.com/cli/
https://docs.aws.amazon.com/cli/latest/reference/configure/
```

*install nvm*
```
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# open ~/.zshrc (or ~/.bashrc if you are using bash), add the following lines

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm

# restart zsh / bash
nvm --version
```

*install node and cdk*
```
nvm install 18
npm install -g aws-cdk
```

*how to init an empty project (no need to run again)*
```
mkdir cloud-infra
cd cloud-infra
cdk init app --language typescript
```

*cdk environment setup*
```
cdk bootstrap
```

## Useful commands

* `npm run build`   compile typescript to js
* `npm run watch`   watch for changes and compile
* `npm run test`    perform the jest unit tests
* `cdk deploy`      deploy this stack to your default AWS account/region
* `cdk diff`        compare deployed stack with current state
* `cdk synth`       emits the synthesized CloudFormation template
