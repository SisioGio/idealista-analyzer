import aws_cdk as cdk
from stack import IdealistaStack
app = cdk.App()
IdealistaStack(app, "IdealistaStack")
app.synth()
