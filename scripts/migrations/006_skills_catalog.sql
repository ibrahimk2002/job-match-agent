-- 006_skills_catalog.sql
-- Skills controlled vocabulary and junction tables.
-- Seed data is added later in this file (see below).

CREATE TABLE IF NOT EXISTS skills_catalog (
    id        SERIAL PRIMARY KEY,
    canonical TEXT NOT NULL UNIQUE,
    category  TEXT NOT NULL CHECK (category IN ('hard', 'soft', 'other')),
    source    TEXT NOT NULL DEFAULT 'curated' CHECK (source IN ('auto', 'curated'))
);

CREATE TABLE IF NOT EXISTS skill_aliases (
    alias    TEXT PRIMARY KEY,
    skill_id INTEGER NOT NULL REFERENCES skills_catalog(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS job_profile_skills (
    job_profile_id INTEGER NOT NULL REFERENCES job_profiles(id) ON DELETE CASCADE,
    skill_id       INTEGER NOT NULL REFERENCES skills_catalog(id) ON DELETE CASCADE,
    importance     TEXT NOT NULL CHECK (importance IN ('must', 'preferred', 'nice')),
    PRIMARY KEY (job_profile_id, skill_id)
);

CREATE TABLE IF NOT EXISTS resume_skills (
    resume_id INTEGER NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    skill_id  INTEGER NOT NULL REFERENCES skills_catalog(id) ON DELETE CASCADE,
    PRIMARY KEY (resume_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_job_profile_skills_skill ON job_profile_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_resume_skills_skill ON resume_skills(skill_id);

-- ============================================================
-- Seed: skills_catalog
-- 235 curated canonical skills across 8 categories.
-- category='hard' for all concrete technologies/tools.
-- category='other' for patterns, concepts, and methodologies.
-- ============================================================

INSERT INTO skills_catalog (canonical, category, source) VALUES
-- Languages (26)
  ('Python',              'hard', 'curated'),
  ('JavaScript',          'hard', 'curated'),
  ('TypeScript',          'hard', 'curated'),
  ('Java',                'hard', 'curated'),
  ('Go',                  'hard', 'curated'),
  ('Rust',                'hard', 'curated'),
  ('C++',                 'hard', 'curated'),
  ('C',                   'hard', 'curated'),
  ('C#',                  'hard', 'curated'),
  ('Ruby',                'hard', 'curated'),
  ('PHP',                 'hard', 'curated'),
  ('Scala',               'hard', 'curated'),
  ('Kotlin',              'hard', 'curated'),
  ('Swift',               'hard', 'curated'),
  ('Dart',                'hard', 'curated'),
  ('R',                   'hard', 'curated'),
  ('MATLAB',              'hard', 'curated'),
  ('Bash',                'hard', 'curated'),
  ('PowerShell',          'hard', 'curated'),
  ('Elixir',              'hard', 'curated'),
  ('Haskell',             'hard', 'curated'),
  ('Lua',                 'hard', 'curated'),
  ('Perl',                'hard', 'curated'),
  ('Groovy',              'hard', 'curated'),
  ('Clojure',             'hard', 'curated'),
  ('Deno',                'hard', 'curated'),

-- Frameworks (28)
  ('React',               'hard', 'curated'),
  ('Angular',             'hard', 'curated'),
  ('Vue.js',              'hard', 'curated'),
  ('Next.js',             'hard', 'curated'),
  ('Nuxt.js',             'hard', 'curated'),
  ('Svelte',              'hard', 'curated'),
  ('SvelteKit',           'hard', 'curated'),
  ('Express.js',          'hard', 'curated'),
  ('Fastify',             'hard', 'curated'),
  ('NestJS',              'hard', 'curated'),
  ('Remix',               'hard', 'curated'),
  ('Gatsby',              'hard', 'curated'),
  ('Django',              'hard', 'curated'),
  ('Flask',               'hard', 'curated'),
  ('FastAPI',             'hard', 'curated'),
  ('Spring Boot',         'hard', 'curated'),
  ('Spring Framework',    'hard', 'curated'),
  ('Ruby on Rails',       'hard', 'curated'),
  ('Laravel',             'hard', 'curated'),
  ('ASP.NET Core',        'hard', 'curated'),
  ('Phoenix',             'hard', 'curated'),
  ('Gin',                 'hard', 'curated'),
  ('Fiber',               'hard', 'curated'),
  ('Actix',               'hard', 'curated'),
  ('htmx',                'hard', 'curated'),
  ('React Native',        'hard', 'curated'),
  ('Flutter',             'hard', 'curated'),
  ('Electron',            'hard', 'curated'),

-- Databases (26)
  ('PostgreSQL',          'hard', 'curated'),
  ('MySQL',               'hard', 'curated'),
  ('SQLite',              'hard', 'curated'),
  ('SQL Server',          'hard', 'curated'),
  ('Oracle Database',     'hard', 'curated'),
  ('MongoDB',             'hard', 'curated'),
  ('Redis',               'hard', 'curated'),
  ('Elasticsearch',       'hard', 'curated'),
  ('Apache Cassandra',    'hard', 'curated'),
  ('Amazon DynamoDB',     'hard', 'curated'),
  ('Firestore',           'hard', 'curated'),
  ('Couchbase',           'hard', 'curated'),
  ('Neo4j',               'hard', 'curated'),
  ('InfluxDB',            'hard', 'curated'),
  ('TimescaleDB',         'hard', 'curated'),
  ('CockroachDB',         'hard', 'curated'),
  ('Snowflake',           'hard', 'curated'),
  ('BigQuery',            'hard', 'curated'),
  ('Amazon Redshift',     'hard', 'curated'),
  ('Databricks',          'hard', 'curated'),
  ('Pinecone',            'hard', 'curated'),
  ('Weaviate',            'hard', 'curated'),
  ('ChromaDB',            'hard', 'curated'),
  ('MariaDB',             'hard', 'curated'),
  ('Supabase',            'hard', 'curated'),
  ('Neon',                'hard', 'curated'),

-- Cloud (30)
  ('AWS',                     'hard', 'curated'),
  ('GCP',                     'hard', 'curated'),
  ('Azure',                   'hard', 'curated'),
  ('AWS Lambda',              'hard', 'curated'),
  ('Amazon EC2',              'hard', 'curated'),
  ('Amazon S3',               'hard', 'curated'),
  ('Amazon RDS',              'hard', 'curated'),
  ('Amazon ECS',              'hard', 'curated'),
  ('Amazon EKS',              'hard', 'curated'),
  ('AWS CDK',                 'hard', 'curated'),
  ('CloudFormation',          'hard', 'curated'),
  ('Google Kubernetes Engine','hard', 'curated'),
  ('Cloud Run',               'hard', 'curated'),
  ('Cloud Functions',         'hard', 'curated'),
  ('Azure Kubernetes Service','hard', 'curated'),
  ('Azure DevOps',            'hard', 'curated'),
  ('Azure Functions',         'hard', 'curated'),
  ('AWS Fargate',             'hard', 'curated'),
  ('Amazon CloudFront',       'hard', 'curated'),
  ('Amazon Route 53',         'hard', 'curated'),
  ('Amazon SQS',              'hard', 'curated'),
  ('Amazon SNS',              'hard', 'curated'),
  ('Amazon API Gateway',      'hard', 'curated'),
  ('Google Cloud Storage',    'hard', 'curated'),
  ('Cloudflare',              'hard', 'curated'),
  ('Vercel',                  'hard', 'curated'),
  ('Netlify',                 'hard', 'curated'),
  ('Heroku',                  'hard', 'curated'),
  ('DigitalOcean',            'hard', 'curated'),
  ('Fly.io',                  'hard', 'curated'),

-- DevOps / Infrastructure (30)
  ('Docker',              'hard', 'curated'),
  ('Kubernetes',          'hard', 'curated'),
  ('Terraform',           'hard', 'curated'),
  ('Ansible',             'hard', 'curated'),
  ('Helm',                'hard', 'curated'),
  ('Jenkins',             'hard', 'curated'),
  ('GitHub Actions',      'hard', 'curated'),
  ('GitLab CI',           'hard', 'curated'),
  ('CircleCI',            'hard', 'curated'),
  ('ArgoCD',              'hard', 'curated'),
  ('FluxCD',              'hard', 'curated'),
  ('Prometheus',          'hard', 'curated'),
  ('Grafana',             'hard', 'curated'),
  ('Datadog',             'hard', 'curated'),
  ('New Relic',           'hard', 'curated'),
  ('Splunk',              'hard', 'curated'),
  ('ELK Stack',           'hard', 'curated'),
  ('Nginx',               'hard', 'curated'),
  ('HAProxy',             'hard', 'curated'),
  ('Istio',               'hard', 'curated'),
  ('Consul',              'hard', 'curated'),
  ('HashiCorp Vault',     'hard', 'curated'),
  ('Pulumi',              'hard', 'curated'),
  ('Packer',              'hard', 'curated'),
  ('Linux',               'hard', 'curated'),
  ('Buildkite',           'hard', 'curated'),
  ('OpenTelemetry',       'hard', 'curated'),
  ('Vagrant',             'hard', 'curated'),
  ('Tekton',              'hard', 'curated'),
  ('Linkerd',             'hard', 'curated'),

-- AI / ML (33)
  ('PyTorch',             'hard', 'curated'),
  ('TensorFlow',          'hard', 'curated'),
  ('scikit-learn',        'hard', 'curated'),
  ('Keras',               'hard', 'curated'),
  ('pandas',              'hard', 'curated'),
  ('NumPy',               'hard', 'curated'),
  ('SciPy',               'hard', 'curated'),
  ('Hugging Face',        'hard', 'curated'),
  ('LangChain',           'hard', 'curated'),
  ('LlamaIndex',          'hard', 'curated'),
  ('OpenAI API',          'hard', 'curated'),
  ('Anthropic API',       'hard', 'curated'),
  ('Vertex AI',           'hard', 'curated'),
  ('Amazon SageMaker',    'hard', 'curated'),
  ('MLflow',              'hard', 'curated'),
  ('Weights & Biases',    'hard', 'curated'),
  ('Ray',                 'hard', 'curated'),
  ('Dask',                'hard', 'curated'),
  ('Apache Spark',        'hard', 'curated'),
  ('Apache Airflow',      'hard', 'curated'),
  ('Prefect',             'hard', 'curated'),
  ('DVC',                 'hard', 'curated'),
  ('ONNX',                'hard', 'curated'),
  ('OpenCV',              'hard', 'curated'),
  ('spaCy',               'hard', 'curated'),
  ('NLTK',                'hard', 'curated'),
  ('XGBoost',             'hard', 'curated'),
  ('LightGBM',            'hard', 'curated'),
  ('CatBoost',            'hard', 'curated'),
  ('Stable Diffusion',    'hard', 'curated'),
  ('Jupyter Notebook',    'hard', 'curated'),
  ('Apache Flink',        'hard', 'curated'),
  ('Triton',              'hard', 'curated'),

-- Other Tools (24)
  ('Git',                 'hard', 'curated'),
  ('GitHub',              'hard', 'curated'),
  ('GitLab',              'hard', 'curated'),
  ('Bitbucket',           'hard', 'curated'),
  ('Jira',                'hard', 'curated'),
  ('Confluence',          'hard', 'curated'),
  ('Postman',             'hard', 'curated'),
  ('Swagger',             'hard', 'curated'),
  ('gRPC',                'hard', 'curated'),
  ('Apache Kafka',        'hard', 'curated'),
  ('RabbitMQ',            'hard', 'curated'),
  ('Celery',              'hard', 'curated'),
  ('Sentry',              'hard', 'curated'),
  ('PagerDuty',           'hard', 'curated'),
  ('Auth0',               'hard', 'curated'),
  ('Okta',                'hard', 'curated'),
  ('Figma',               'hard', 'curated'),
  ('Storybook',           'hard', 'curated'),
  ('Webpack',             'hard', 'curated'),
  ('Vite',                'hard', 'curated'),
  ('Playwright',          'hard', 'curated'),
  ('Cypress',             'hard', 'curated'),
  ('Jest',                'hard', 'curated'),
  ('Docker Compose',      'hard', 'curated'),

-- Concepts / Patterns (38)
  ('REST APIs',                   'other', 'curated'),
  ('GraphQL',                     'other', 'curated'),
  ('Microservices',               'other', 'curated'),
  ('Event-Driven Architecture',   'other', 'curated'),
  ('Domain-Driven Design',        'other', 'curated'),
  ('Test-Driven Development',     'other', 'curated'),
  ('CI/CD',                       'other', 'curated'),
  ('Agile',                       'other', 'curated'),
  ('Scrum',                       'other', 'curated'),
  ('Kanban',                      'other', 'curated'),
  ('System Design',               'other', 'curated'),
  ('Distributed Systems',         'other', 'curated'),
  ('Cloud-Native',                'other', 'curated'),
  ('Serverless',                  'other', 'curated'),
  ('Infrastructure as Code',      'other', 'curated'),
  ('DevOps',                      'other', 'curated'),
  ('GitOps',                      'other', 'curated'),
  ('Observability',               'other', 'curated'),
  ('Data Pipelines',              'other', 'curated'),
  ('ETL',                         'other', 'curated'),
  ('API Design',                  'other', 'curated'),
  ('OAuth 2.0',                   'other', 'curated'),
  ('JWT',                         'other', 'curated'),
  ('Object-Oriented Programming', 'other', 'curated'),
  ('Functional Programming',      'other', 'curated'),
  ('Design Patterns',             'other', 'curated'),
  ('SOLID Principles',            'other', 'curated'),
  ('Clean Architecture',          'other', 'curated'),
  ('Hexagonal Architecture',      'other', 'curated'),
  ('Event Sourcing',              'other', 'curated'),
  ('CQRS',                        'other', 'curated'),
  ('Service Mesh',                'other', 'curated'),
  ('RAG',                         'other', 'curated'),
  ('Prompt Engineering',          'other', 'curated'),
  ('LLM Fine-tuning',             'other', 'curated'),
  ('Multi-Agent Systems',         'other', 'curated'),
  ('WebAssembly',                 'other', 'curated'),
  ('Zero-Trust Security',         'other', 'curated')
ON CONFLICT (canonical) DO NOTHING;

-- ============================================================
-- Seed: skill_aliases
-- Lowercase only. One INSERT per canonical that has aliases.
-- Subquery approach avoids hardcoded IDs.
-- ============================================================

-- Languages
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['python3','py','cpython']), id
FROM skills_catalog WHERE canonical = 'Python'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['js','node.js','nodejs','node']), id
FROM skills_catalog WHERE canonical = 'JavaScript'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['ts']), id
FROM skills_catalog WHERE canonical = 'TypeScript'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['golang']), id
FROM skills_catalog WHERE canonical = 'Go'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['cpp','c plus plus']), id
FROM skills_catalog WHERE canonical = 'C++'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['csharp','dotnet','.net']), id
FROM skills_catalog WHERE canonical = 'C#'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['rb']), id
FROM skills_catalog WHERE canonical = 'Ruby'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['shell','shell scripting','bash scripting']), id
FROM skills_catalog WHERE canonical = 'Bash'
ON CONFLICT DO NOTHING;

-- Frameworks
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['reactjs','react.js']), id
FROM skills_catalog WHERE canonical = 'React'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['angularjs']), id
FROM skills_catalog WHERE canonical = 'Angular'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['vue','vuejs','vue3','vue 3']), id
FROM skills_catalog WHERE canonical = 'Vue.js'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['nextjs','next js']), id
FROM skills_catalog WHERE canonical = 'Next.js'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['nuxt','nuxtjs']), id
FROM skills_catalog WHERE canonical = 'Nuxt.js'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['express']), id
FROM skills_catalog WHERE canonical = 'Express.js'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['spring-boot']), id
FROM skills_catalog WHERE canonical = 'Spring Boot'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['spring']), id
FROM skills_catalog WHERE canonical = 'Spring Framework'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['rails','ror']), id
FROM skills_catalog WHERE canonical = 'Ruby on Rails'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['asp.net','aspnet','asp.net core']), id
FROM skills_catalog WHERE canonical = 'ASP.NET Core'
ON CONFLICT DO NOTHING;

-- Databases
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['postgres','psql','pgsql','pg']), id
FROM skills_catalog WHERE canonical = 'PostgreSQL'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['mssql','microsoft sql server','ms sql server']), id
FROM skills_catalog WHERE canonical = 'SQL Server'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['oracle']), id
FROM skills_catalog WHERE canonical = 'Oracle Database'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['mongo']), id
FROM skills_catalog WHERE canonical = 'MongoDB'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['elastic','es','opensearch']), id
FROM skills_catalog WHERE canonical = 'Elasticsearch'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['cassandra']), id
FROM skills_catalog WHERE canonical = 'Apache Cassandra'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['dynamodb','dynamo']), id
FROM skills_catalog WHERE canonical = 'Amazon DynamoDB'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['redshift']), id
FROM skills_catalog WHERE canonical = 'Amazon Redshift'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['bq']), id
FROM skills_catalog WHERE canonical = 'BigQuery'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['maria','mariadb']), id
FROM skills_catalog WHERE canonical = 'MariaDB'
ON CONFLICT DO NOTHING;

-- Cloud
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['amazon web services','amazon aws']), id
FROM skills_catalog WHERE canonical = 'AWS'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['google cloud','google cloud platform']), id
FROM skills_catalog WHERE canonical = 'GCP'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['microsoft azure']), id
FROM skills_catalog WHERE canonical = 'Azure'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['lambda']), id
FROM skills_catalog WHERE canonical = 'AWS Lambda'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['ec2']), id
FROM skills_catalog WHERE canonical = 'Amazon EC2'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['s3']), id
FROM skills_catalog WHERE canonical = 'Amazon S3'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['rds']), id
FROM skills_catalog WHERE canonical = 'Amazon RDS'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['ecs']), id
FROM skills_catalog WHERE canonical = 'Amazon ECS'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['eks']), id
FROM skills_catalog WHERE canonical = 'Amazon EKS'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['gke']), id
FROM skills_catalog WHERE canonical = 'Google Kubernetes Engine'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['aks']), id
FROM skills_catalog WHERE canonical = 'Azure Kubernetes Service'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['sqs']), id
FROM skills_catalog WHERE canonical = 'Amazon SQS'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['sns']), id
FROM skills_catalog WHERE canonical = 'Amazon SNS'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['gcs']), id
FROM skills_catalog WHERE canonical = 'Google Cloud Storage'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['aws cloudformation']), id
FROM skills_catalog WHERE canonical = 'CloudFormation'
ON CONFLICT DO NOTHING;

-- DevOps
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['k8s']), id
FROM skills_catalog WHERE canonical = 'Kubernetes'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['gitlab-ci','gitlab ci/cd']), id
FROM skills_catalog WHERE canonical = 'GitLab CI'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['flux']), id
FROM skills_catalog WHERE canonical = 'FluxCD'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['vault']), id
FROM skills_catalog WHERE canonical = 'HashiCorp Vault'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['ubuntu','debian','centos','rhel']), id
FROM skills_catalog WHERE canonical = 'Linux'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['github-actions']), id
FROM skills_catalog WHERE canonical = 'GitHub Actions'
ON CONFLICT DO NOTHING;

-- AI / ML
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['torch']), id
FROM skills_catalog WHERE canonical = 'PyTorch'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['sklearn','scikit']), id
FROM skills_catalog WHERE canonical = 'scikit-learn'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['huggingface']), id
FROM skills_catalog WHERE canonical = 'Hugging Face'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['llama-index','llama index']), id
FROM skills_catalog WHERE canonical = 'LlamaIndex'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['openai']), id
FROM skills_catalog WHERE canonical = 'OpenAI API'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['anthropic']), id
FROM skills_catalog WHERE canonical = 'Anthropic API'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['sagemaker']), id
FROM skills_catalog WHERE canonical = 'Amazon SageMaker'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['wandb','w&b']), id
FROM skills_catalog WHERE canonical = 'Weights & Biases'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['spark','pyspark']), id
FROM skills_catalog WHERE canonical = 'Apache Spark'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['airflow']), id
FROM skills_catalog WHERE canonical = 'Apache Airflow'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['jupyter','jupyter lab']), id
FROM skills_catalog WHERE canonical = 'Jupyter Notebook'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['cv2']), id
FROM skills_catalog WHERE canonical = 'OpenCV'
ON CONFLICT DO NOTHING;

-- Other Tools
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['kafka']), id
FROM skills_catalog WHERE canonical = 'Apache Kafka'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['openapi','open api']), id
FROM skills_catalog WHERE canonical = 'Swagger'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['grpc']), id
FROM skills_catalog WHERE canonical = 'gRPC'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['docker-compose','docker compose']), id
FROM skills_catalog WHERE canonical = 'Docker Compose'
ON CONFLICT DO NOTHING;

-- Concepts
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['rest','restful','rest api','http api']), id
FROM skills_catalog WHERE canonical = 'REST APIs'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['eda','event driven architecture']), id
FROM skills_catalog WHERE canonical = 'Event-Driven Architecture'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['ddd']), id
FROM skills_catalog WHERE canonical = 'Domain-Driven Design'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['tdd']), id
FROM skills_catalog WHERE canonical = 'Test-Driven Development'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['iac']), id
FROM skills_catalog WHERE canonical = 'Infrastructure as Code'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['oop','object oriented programming']), id
FROM skills_catalog WHERE canonical = 'Object-Oriented Programming'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['fp']), id
FROM skills_catalog WHERE canonical = 'Functional Programming'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['oauth','oauth2']), id
FROM skills_catalog WHERE canonical = 'OAuth 2.0'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['wasm']), id
FROM skills_catalog WHERE canonical = 'WebAssembly'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['retrieval-augmented generation','retrieval augmented generation']), id
FROM skills_catalog WHERE canonical = 'RAG'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['continuous integration','continuous deployment','continuous delivery']), id
FROM skills_catalog WHERE canonical = 'CI/CD'
ON CONFLICT DO NOTHING;
