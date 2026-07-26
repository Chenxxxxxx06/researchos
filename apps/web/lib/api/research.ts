/**
 * Barrel for the research API surface. Split into `./papers` and `./ideas`;
 * this keeps any external `@/lib/api/research` import path stable.
 */
export * from './papers';
export * from './ideas';
