from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    Duration,
)
from constructs import Construct

class IdealistaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        
        role = iam.Role(self, "idealista-scraper-lambda-role",
                        assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        secret_arn='arn:aws:secretsmanager:eu-central-1:495348364820:secret:idealista-keys-oQ6s6l'
        rds_secret_arn='arn:aws:secretsmanager:eu-central-1:495348364820:secret:rds!db-efc52989-89c8-4009-a2c3-e211a33ba1bd-MuKnTg'
        openai_secret_arn='arn:aws:secretsmanager:eu-central-1:495348364820:secret:openai-api-key-dzeB13'
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
                resources=[secret_arn, rds_secret_arn, openai_secret_arn]
            )
        )
        # Layer for lambdas
        utils_layer = _lambda.LayerVersion(
            self, "UtilsLayer",
            code=_lambda.Code.from_asset("layer"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Shared utils"
        )
        
        
        #  Lambda function
        scraper = _lambda.Function(
            self, "idealista-scraper-lambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambda_handler.main",
            code=_lambda.Code.from_asset("src"),
            role=role,
            layers=[utils_layer],
            timeout=Duration.minutes(15),
        
        )

        # 2. Schedule expressions (CRON)
        schedule_times = ["8", "15", "20"]  # hours in UTC

        for hour in schedule_times:
            rule = events.Rule(
                self,
                f"ScheduleRule{hour}",
                schedule=events.Schedule.cron(minute="0", hour=hour)
            )
            rule.add_target(targets.LambdaFunction(scraper))
            
            
