import { createServer, IncomingMessage, ServerResponse } from 'http';
import { join } from 'path';
import {
  createLearningController,
  createNeuralCoreMiddleware,
  ContinuousLearningEngine,
  DeterministicCoreAdapter,
  FileLearningStoreProvider,
  InMemoryTelemetryStore,
} from './index';
import { HttpRequest, HttpResponse } from './types';

const PORT = Number(process.env.PORT ?? 4000);
const HOST = process.env.HOST ?? '0.0.0.0';
const ROOT = process.cwd();
const TEMPLATE_PATH = join(ROOT, 'prompts', 'system', 'neural_core.yaml');
const LEARNING_STORE_PATH = join(ROOT, 'data', 'learning', 'state.json');

function sendJson(res: ServerResponse, status: number, body: unknown): void {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload),
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  });
  res.end(payload);
}

async function readJsonBody(req: IncomingMessage): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }

  if (chunks.length === 0) {
    return {};
  }

  const raw = Buffer.concat(chunks).toString('utf-8');
  if (raw.trim() === '') return {};
  return JSON.parse(raw) as Record<string, unknown>;
}

function toMiddlewareResponse(res: ServerResponse): HttpResponse {
  let statusCode = 200;

  const response: HttpResponse = {
    status(code: number) {
      statusCode = code;
      return response;
    },
    json(body: unknown) {
      sendJson(res, statusCode, body);
      return response;
    },
  };

  return response;
}

function parseSearchParams(url: string | undefined): Record<string, string> {
  if (!url || !url.includes('?')) return {};
  const query = url.split('?')[1] ?? '';
  const result: Record<string, string> = {};
  for (const [key, value] of new URLSearchParams(query)) {
    result[key] = value;
  }
  return result;
}

function notFound(res: ServerResponse): void {
  sendJson(res, 404, { error: 'Not found' });
}

async function main(): Promise<void> {
  const telemetry = new InMemoryTelemetryStore();
  const learningProvider = new FileLearningStoreProvider(LEARNING_STORE_PATH);
  const learningStore = await learningProvider.load();
  const learningEngine = new ContinuousLearningEngine({ store: learningStore });
  learningEngine.installDefaultSchedules();
  await learningProvider.persist(learningStore);

  const handler = createNeuralCoreMiddleware({
    systemTemplatePath: TEMPLATE_PATH,
    complexityThreshold: 1,
    defaultPolitenessTier: 'neutral',
    telemetry,
    coreAdapter: new DeterministicCoreAdapter(),
    learning: { store: learningStore },
  });

  const learningController = createLearningController(
    { store: learningStore },
    { engine: learningEngine },
  );

  async function runLearningRequest(
    _req: IncomingMessage,
    res: ServerResponse,
    body: Record<string, unknown>,
    method: string,
    url: string,
  ): Promise<void> {
    const middlewareRequest: HttpRequest & { method: string; url: string } = {
      method,
      url,
      body,
    };
    const middlewareResponse = toMiddlewareResponse(res);
    await learningController(
      middlewareRequest,
      middlewareResponse,
      (err) => {
        if (err) {
          const message = err instanceof Error ? err.message : 'Unknown error';
          sendJson(res, 500, { error: message });
        }
      },
    );
    await learningProvider.persist(learningStore);
  }

  const server = createServer(async (req, res) => {
    const method = req.method ?? 'GET';
    const url = req.url ?? '/';

    if (method === 'OPTIONS') {
      res.writeHead(204, {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
      });
      res.end();
      return;
    }

    if (method === 'GET' && url === '/health') {
      sendJson(res, 200, { status: 'ok', service: 'neural-orchestrator' });
      return;
    }

    if (method === 'GET' && url === '/') {
      sendJson(res, 200, {
        service: 'neural-orchestrator',
        endpoints: {
          health: 'GET /health',
          task: 'POST /api/task',
          learning: {
            outcomes: 'POST /learning/outcomes',
            feedback: 'POST /learning/feedback',
            state: 'GET /learning/state',
            research: 'GET /learning/research?taskDescription=...',
            guidance: 'POST /learning/guidance',
            schedulesRun: 'POST /learning/schedules/run',
            schedulesInstall: 'POST /learning/schedules/install-defaults',
          },
        },
        example: {
          method: 'POST',
          path: '/api/task',
          body: {
            taskDescription: 'Solve the 0/1 knapsack problem with dynamic programming.',
            isComplexWorkflow: true,
            domainHint: 'dev_dp',
            algorithmTag: 'knapsack_01',
            politenessTier: 'neutral',
          },
        },
      });
      return;
    }

    if (method === 'GET' && url.startsWith('/learning/research')) {
      await runLearningRequest(req, res, parseSearchParams(url), 'GET', '/learning/research');
      return;
    }

    if (method === 'GET' && url === '/learning/state') {
      await runLearningRequest(req, res, {}, 'GET', url);
      return;
    }

    const learningEndpoints = [
      '/learning/outcomes',
      '/learning/feedback',
      '/learning/guidance',
      '/learning/schedules/run',
      '/learning/schedules/install-defaults',
    ];
    if (method === 'POST' && learningEndpoints.includes(url)) {
      try {
        const body = await readJsonBody(req);
        await runLearningRequest(req, res, body, method, url);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Invalid JSON body';
        sendJson(res, 400, { error: message });
      }
      return;
    }

    if (method === 'POST' && url === '/api/task') {
      try {
        const body = await readJsonBody(req);
        const middlewareReq: HttpRequest = {
          body: {
            taskDescription: typeof body.taskDescription === 'string' ? body.taskDescription : undefined,
            isComplexWorkflow: body.isComplexWorkflow === true,
            domainHint: body.domainHint as HttpRequest['body']['domainHint'],
            algorithmTag: typeof body.algorithmTag === 'string' ? body.algorithmTag : undefined,
            politenessTier: body.politenessTier as HttpRequest['body']['politenessTier'],
          },
        };

        await handler(middlewareReq, toMiddlewareResponse(res), (err) => {
          if (err) {
            const message = err instanceof Error ? err.message : 'Unknown error';
            sendJson(res, 500, { error: message });
          }
        });
        await learningProvider.persist(learningStore);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Invalid JSON body';
        sendJson(res, 400, { error: message });
      }
      return;
    }

    notFound(res);
  });

  server.listen(PORT, HOST, () => {
    console.log(`neural-orchestrator listening on http://${HOST}:${PORT}`);
    console.log('Endpoints: GET /health, GET /, POST /api/task');
    console.log('Learning endpoints: /learning/*');
    console.log(`Learning store: ${LEARNING_STORE_PATH}`);
    console.log('Expose publicly with: npm run tunnel');
  });
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
