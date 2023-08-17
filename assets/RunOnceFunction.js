var AWS = require('aws-sdk');

const projectName = process.env.CODE_BUILD_PROJECT_NAME;

exports.lambdaHandler = async (event, context) => {
    try {

        var codebuild = new AWS.CodeBuild();
        const codebuildParams = {
            projectName: projectName,
        };
        const codebuildResponse = await codebuild.startBuild(codebuildParams).promise();
        console.log('codebuildResponse: ', codebuildResponse);

        return {
            statusCode: 200,
            body: JSON.stringify('done'),
        };
    } catch (err) {
        console.log('err: ', err);
    }
};