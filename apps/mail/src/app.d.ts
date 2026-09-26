import type { SagantaLocals } from '@saganta/auth';

declare global {
  namespace App {
    interface Locals extends SagantaLocals {}
    interface PageData {
      user?: import('@saganta/auth').SagantaUser;
    }
  }
}

export {};
