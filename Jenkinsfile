pipeline {
    agent any

    options {
        timeout(time: 60, unit: 'MINUTES')
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    parameters {
        booleanParam(name: 'ENABLE_DEPLOYMENT', defaultValue: false, description: 'Enable the explicitly configured deployment stage.')
        string(name: 'DEPLOY_TARGET', defaultValue: '', description: 'Configured deployment target identifier; leave empty to skip deployment.')
        string(name: 'DEPLOY_CREDENTIALS_ID', defaultValue: '', description: 'Optional Jenkins Secret Text credential ID exposed as DEPLOY_TOKEN only during deployment.')
    }

    environment {
        EXECUTION_MODE = 'simulation'
        ALLOW_AWS_SCAN = 'false'
        DOCKER_BUILDKIT = '1'
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }
        stage('Environment Validation') {
            steps {
                sh '''
                    set -eu
                    python --version
                    node --version
                    npm --version
                    docker --version
                    command -v trivy
                    test -f requirements.txt
                    test -f frontend/package-lock.json
                    echo "EXECUTION_MODE=${EXECUTION_MODE}; live AWS scans disabled"
                '''
            }
        }
        stage('Backend Dependency Installation') {
            steps { sh 'python -m pip install --upgrade pip && python -m pip install -r requirements.txt' }
        }
        stage('Backend Tests') {
            steps { sh 'python -m unittest discover -s tests -v' }
            post { always { junit allowEmptyResults: true, testResults: 'test-results/*.xml' } }
        }
        stage('Frontend Dependency Installation') {
            steps { dir('frontend') { sh 'npm ci' } }
        }
        stage('Frontend Linting') {
            steps { dir('frontend') { sh 'npm run lint' } }
        }
        stage('Frontend Production Build') {
            steps {
                dir('frontend') { sh 'npm run build' }
                archiveArtifacts artifacts: 'frontend/dist/**', fingerprint: true
            }
        }
        stage('Backend Docker Build') {
            steps { sh 'docker build --file backend/Dockerfile --tag autonomous-finops-backend:${BUILD_NUMBER} .' }
        }
        stage('Frontend Docker Build') {
            steps { sh 'docker build --file frontend/Dockerfile --tag autonomous-finops-frontend:${BUILD_NUMBER} .' }
        }
        stage('Docker Image Validation') {
            steps {
                sh '''
                    docker image inspect autonomous-finops-backend:${BUILD_NUMBER} >/dev/null
                    docker image inspect autonomous-finops-frontend:${BUILD_NUMBER} >/dev/null
                    test "$(docker image inspect --format='{{.Config.User}}' autonomous-finops-backend:${BUILD_NUMBER})" = "10001:10001"
                    echo "Both images exist; backend runs as UID/GID 10001"
                '''
            }
        }
        stage('Trivy Security Scan') {
            steps {
                sh 'trivy image --severity HIGH,CRITICAL --exit-code 1 autonomous-finops-backend:${BUILD_NUMBER}'
                sh 'trivy image --severity HIGH,CRITICAL --exit-code 1 autonomous-finops-frontend:${BUILD_NUMBER}'
                sh 'trivy fs --scanners vuln,misconfig,secret --severity HIGH,CRITICAL --exit-code 1 .'
            }
        }
        stage('Deployment') {
            when {
                allOf {
                    expression { params.ENABLE_DEPLOYMENT }
                    expression { params.DEPLOY_TARGET?.trim() }
                    expression { env.DEPLOY_COMMAND?.trim() }
                }
            }
            steps {
                input message: "Deploy this verified build to ${params.DEPLOY_TARGET}?", ok: 'Deploy'
                script {
                    if (params.DEPLOY_CREDENTIALS_ID?.trim()) {
                        withCredentials([string(credentialsId: params.DEPLOY_CREDENTIALS_ID, variable: 'DEPLOY_TOKEN')]) {
                            sh 'set +x; eval "$DEPLOY_COMMAND"'
                        }
                    } else {
                        sh 'set +x; eval "$DEPLOY_COMMAND"'
                    }
                }
            }
            post {
                success { echo 'Configured deployment command completed. Configure its post-deploy health check in DEPLOY_COMMAND.' }
            }
        }
    }

    post {
        always { echo "Build ${BUILD_NUMBER} completed with result: ${currentBuild.currentResult}" }
        failure { echo 'Pipeline failed. Review the first failing stage and its console output.' }
        cleanup {
            sh 'docker image rm -f autonomous-finops-backend:${BUILD_NUMBER} autonomous-finops-frontend:${BUILD_NUMBER} >/dev/null 2>&1 || true'
        }
    }
}
